# Ultravox Stages Example

## Overview

This is a simple example demonstrating stages in Ultravox.

Stages are a mechanism for breaking up a call into multiple stages, or steps. Each stage has its own configuration (system prompt, tools, etc). Stages can be a better alternative than one giant prompt.

We always recommend starting simple first (i.e., only a single call stage) and then adding more stages as needed if/when the situation calls for it. Typically, stages are necessary when the LLM is struggling to perform a task or when the task is too complex for a single prompt.

## Getting Started

1. Clone this repository
1. Install https://fastht.ml/ with pip install python-fasthtml
1. Get an API key from https://app.ultravox.ai and either set it as an environment variable under ULTRAVOX_API_KEY or replace the value in main.py
1. Install ngrok from https://ngrok.com/download
1. Run python main.py
1. Run `ngrok http 5001`
1. Copy the ngrok URL and replace `TOOL_URL` in `main.py`
1. Open your browser to http://localhost:5001
