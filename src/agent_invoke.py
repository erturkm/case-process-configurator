"""Proven Copilot Studio direct-invoke recipe (verified live 2026-09-13).

Route   : POST https://{HOST}/copilotstudio/dataverse-backed/authenticated/bots/{schemaname}/conversations
          POST .../conversations/{conversationId}?api-version=2022-03-01-preview
Body    : {"activity": {...}}   <-- MUST be wrapped; a bare activity returns HTTP 400
Host    : raw hex of environment id, dashes stripped, split 30 + last 2
Scope   : https://api.powerplatform.com/CopilotStudio.Copilots.Invoke
Access  : the calling identity must be SHARED on the bot record, else the bot
          replies "You don't have access to talk to this bot" with trace
          ErrorCode=AccessToBotDenied (HTTP 200 - check the trace, not the status).
"""
import json, urllib.request

ENV_ID = "ad5dd938-824d-e154-aac2-97f7c4678f5a"
API = "api-version=2022-03-01-preview"


def host(env_id=ENV_ID):
    h = env_id.replace("-", "")
    return f"{h[:-2]}.{h[-2:]}.environment.api.powerplatform.com"


def _call(method, url, token, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:400]}") from None


def ask(bot_schemaname, prompt, token, env_id=ENV_ID):
    """Start a conversation, send the prompt, return (text, raw_activities)."""
    base = (f"https://{host(env_id)}/copilotstudio/dataverse-backed"
            f"/authenticated/bots/{bot_schemaname}")
    conv = _call("POST", f"{base}/conversations?{API}", token, {})
    cid = conv["conversationId"]

    for a in conv.get("activities", []):
        v = a.get("value")
        if a.get("type") == "trace" and isinstance(v, dict) and v.get("ErrorCode"):
            raise RuntimeError(f"agent refused: {v['ErrorCode']} "
                               f"(share the bot record with the caller)")

    res = _call("POST", f"{base}/conversations/{cid}?{API}", token,
                {"activity": {"type": "message", "text": prompt}})

    parts = [a["text"] for a in res.get("activities", [])
             if a.get("type") == "message"
             and (a.get("from") or {}).get("role") == "bot"
             and a.get("text", "").strip()]
    return "\n\n".join(parts), res.get("activities", [])


if __name__ == "__main__":
    import sys
    tok = open("/tmp/_svctoken").read().strip()
    txt, _ = ask(sys.argv[1] if len(sys.argv) > 1 else "new_FraudDisputeTriage",
                 sys.argv[2] if len(sys.argv) > 2 else "Hello, what do you do?", tok)
    print(txt)
