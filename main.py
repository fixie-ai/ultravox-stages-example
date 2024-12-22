from fasthtml.common import (
    fast_app,
    Script,
    Main,
    Div,
    Button,
    H1,
    Span,
    serve,
    Response,
)
from datetime import datetime
import requests
import os
import json

ULTRAVOX_API_KEY = os.environ.get('ULTRAVOX_API_KEY', "<your ultravox api key>")

# Ultravox calls out to your tool over HTTP, so in debug mode, we need to expose the tool to the internet. A simple way to do that is with ngrok. Install ngrok, then run `ngrok http 5001` to expose your local server to the internet. Update this URL with the ngrok URL.
TOOL_URL = "https://<your-path>.ngrok.app"

app, rt = fast_app(pico=False, hdrs=(Script(src="https://cdn.tailwindcss.com"),))

def fixie_request(method, path, **kwargs):
    u = "https://api.ultravox.ai/api"
    return requests.request(
        method, u + path, headers={"X-API-Key": ULTRAVOX_API_KEY}, **kwargs
    )

# We're going to define a single tool to handle navigating between stages
# This tool will be used to navigate between the GREETING, SCHEDULE, and RESCHEDULE stages
NAVIGATE_STAGE_TOOL = {
    "temporaryTool": {
        "modelToolName": "navigateStage",
        "description": "After determining if a new stage is necessary, call this tool to navigate to the next appropriate stage.",
        # Dynamic parameters are params that you need the LLM to provider
        "dynamicParameters": [
            {
                "name": "stageName",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "The stage to navigate to",
                    "type": "string",
                    "enum": ["GREETING", "SCHEDULE", "RESCHEDULE"],
                },
                "required": True,
            }
        ],
        # This is for passing in the call ID to every tool request, useful for logging, keeping state, etc
        "automaticParameters": [
            {
                "name": "call_id",
                "location": "PARAMETER_LOCATION_BODY",
                "knownValue": "KNOWN_PARAM_CALL_ID",
            }
        ],
        "http": {
            "baseUrlPattern": f"{TOOL_URL}/navigateStage",
            "httpMethod": "POST",
        },
    }
}

# We're going to define a tool to handle scheduling events
# We could wrap this around cal.com or some other scheduling service (or build our own)
SCHEDULE_EVENT_TOOL = {
    "temporaryTool": {
        "modelToolName": "scheduleEvent",
        "description": "Schedule an event with the user after collecting the necessary information",
        "dynamicParameters": [
            {
                "name": "attendeeName",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "The user's name",
                    "type": "string",
                },
                "required": True,
            },
            {
                "name": "attendeeEmail",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "The user's name",
                    "type": "string",
                },
                "required": True,
            },
            {
                "name": "startTime",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "The date and start time of the event, expressed as UTC date string (e.g., 2024-08-13T09:00:00Z)",
                    "type": "string",
                },
                "required": True,
            },
            {
                "name": "lengthInMinutes",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "The number of minutes of the meeting",
                    "type": "number",
                },
                "required": True,
            },
        ],
        "automaticParameters": [
            {
                "name": "call_id",
                "location": "PARAMETER_LOCATION_BODY",
                "knownValue": "KNOWN_PARAM_CALL_ID",
            }
        ],
        "http": {
            "baseUrlPattern": f"{TOOL_URL}/scheduleEvent",
            "httpMethod": "POST",
        },
    }
}

STAGES = {
    "GREETING": {
        "systemPrompt": f"You're a helpful scheduling assistant. Today is {datetime.now().strftime('%B %d, %Y')}. You need to politely figure out if the user is trying to schedule a new appointment or reschedule an existing one. Once you know, you must immediately call the navigateStage tool. Don't mention anything about stages to the user.",
        "selectedTools": [NAVIGATE_STAGE_TOOL],
    },
    "SCHEDULE": {
        "systemPrompt": f"You're a helpful scheduling assistant. Today is {datetime.now().strftime('%B %d, %Y')}. You need to collect the necessary information to schedule an event. Once you have the information, you must call the scheduleEvent tool. There is no need to confirm availability. Don't mention anything about stages to the user.",
        "selectedTools": [NAVIGATE_STAGE_TOOL, SCHEDULE_EVENT_TOOL],
    },
    "RESCHEDULE": {
        "systemPrompt": "You're a rescheduling assistant.",
        "selectedTools": [NAVIGATE_STAGE_TOOL],
    },
}

# This is the script that will be loaded when the page is loaded
# We import the Ultravox JS SDK and create a new session
js_on_load = """
import { UltravoxSession } from 'https://esm.sh/ultravox-client';
const debugMessages = new Set(["debug"]);
window.UVSession = new UltravoxSession({ experimentalMessages: debugMessages });
"""

# This is the client side JS that will be run when the call is started
# It will join the call and set up event listeners for status, transcripts, and debug messages
def client_js(callDetails):
    return f"""
    async function joinCall() {{
        const callStatus = await window.UVSession.joinCall("{callDetails.get('joinUrl')}");
        console.log(callStatus);
    }}

    window.UVSession.addEventListener('status', (e) => {{
        let statusDiv = htmx.find("#call-status")
        statusDiv.innerText = e.target._status;
    }});

    window.UVSession.addEventListener('transcripts', (e) => {{
        let transcripts = e.target._transcripts;
        transcript = htmx.find("#transcript");
        transcript.innerText = transcripts.filter(t => t && t.speaker !== "user").map(t => t ? t.text : "").join("\\n");
    }});

    window.UVSession.addEventListener('experimental_message', (msg) => {{
      console.log('Debug: ', JSON.stringify(msg));
    }});

    joinCall();

    htmx.on("#end-call", "click", async (e) => {{
        try {{
            await UVSession.leaveCall();
        }} catch (error) {{
            console.error("Error leaving call:", error);
        }}
    }})
    """

# This just makes the button look nice-ish
TW_BUTTON = "bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mt-4"


def layout(*args, **kwargs):
    return Main(
        # HTML Navigation
        Div(
            Div(*args, **kwargs, cls="mx-auto max-w-3xl"),
            cls="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8",
        )
    )

# This is the main route that will be hit when the page is loaded
# It will return a button that will start the call
@rt("/")
def get():
    button = Button("Start call", hx_post="/start", hx_target="#call-mgmt", hx_swap="outerHTML", cls=TW_BUTTON)
    return layout(
        Script(js_on_load, type="module"),
        H1("Ultravox Stages Example", cls="text-xl font-bold mt-8"),
        Div(
            Div(
                "Status: ",
                Span("Waiting", id="call-status", cls="font-bold"),
            ),
            Div(
                "Call ID:",
                Span("N/A", id="call-id", cls="font-bold"),
            ),
            Div(button),
            id="call-mgmt"
        ),
    )


# This route will be hit when the LLM calls the navigateStage tool
# It will return the system prompt and selected tools for the next stage, along with appopriate headers
# Note the X-Ultravox-Response-Type header, which tells Ultravox to expect a new stage
@rt("/navigateStage")
async def post(req):
    body = await req.json()
    response_body = {
        "systemPrompt": STAGES[body.get("stageName")].get("systemPrompt"),
        "selectedTools": STAGES[body.get("stageName")].get("selectedTools"),
    }
    return Response(
        status_code=200,
        headers={"X-Ultravox-Response-Type": "new-stage"},
        content=json.dumps(response_body),
        media_type="application/json",
    )


@rt("/scheduleEvent")
def post(body):
    print("POST to /scheduleEvent")
    print(body)
    return Response(
        status_code=200,
        content="Event successfully created",
    )


@rt("/start")
async def post():
    d = {
        "systemPrompt": STAGES["GREETING"]["systemPrompt"],
        "voice": "Mark",
        "selectedTools": STAGES["GREETING"]["selectedTools"],
    }
    r = fixie_request("POST", "/calls", json=d)
    if r.status_code == 201:
        callDetails = r.json()
        js = client_js(callDetails)
        return Div(
            Div(
                "Status: ",
                Span("Initializing", id="call-status", cls="font-bold"),
            ),
            Div(
                "Call ID: ",
                Span(callDetails.get("callId"), id="call-id", cls="font-bold"),
            ),
            Button("End call", id="end-call", cls=TW_BUTTON, hx_get="/end", hx_swap="outerHTML"),
            Div("", id="transcript"),
            Script(code=js),
        )
    else:
        print(r.text)
        return r.text

@rt("/end")
def get():
    return Button("Restart", cls=TW_BUTTON, hx_get="/", hx_target="body", hx_boost="false")

serve()
