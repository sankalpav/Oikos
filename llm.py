"""Thin wrapper around GPT-5.6 Terra on Amazon Bedrock (OpenAI-compatible Responses API)."""

import json
import os
import re

REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("MODEL_ID", "global.openai.gpt-5.6-terra")
BASE_URL = os.getenv("OPENAI_BASE_URL", f"https://bedrock-runtime.{REGION}.amazonaws.com/openai/v1")

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            from aws_bedrock_token_generator import provide_token

            key = provide_token(region=REGION)
        _client = OpenAI(base_url=BASE_URL, api_key=key)
    return _client


def reset_client():
    global _client
    _client = None


def _parse_json(text):
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def complete_json(system, user):
    """Call the model and return parsed JSON. Raises on any failure so callers can fall back."""
    resp = _get_client().responses.create(model=MODEL_ID, instructions=system, input=user)
    return _parse_json(resp.output_text)


def ping():
    resp = _get_client().responses.create(model=MODEL_ID, input="Reply with the single word: ready")
    return resp.output_text.strip()
