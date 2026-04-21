import time
from anthropic import Anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request


class BatchClient:
    def __init__(self, api_key: str, model: str, poll_interval: int = 30):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.poll_interval = poll_interval

    def _build_params(self, system, user_prompt, max_tokens):
        params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self.model.startswith("claude-opus-4-7") or self.model.startswith("claude-opus-4-6") or self.model.startswith("claude-sonnet-4-6"):
            params["thinking"] = {"type": "adaptive"}
        return params

    def build_request(self, custom_id: str, system, user_prompt: str, max_tokens: int) -> Request:
        params = self._build_params(system, user_prompt, max_tokens)
        return Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(**params))

    def submit_and_wait(self, requests: list, label: str = "") -> dict:
        if not requests:
            return {}
        print(f"  Submitting batch ({len(requests)} requests) {label}...")
        batch = self.client.messages.batches.create(requests=requests)
        batch_id = batch.id
        print(f"  Batch ID: {batch_id}")

        start = time.time()
        while True:
            batch = self.client.messages.batches.retrieve(batch_id)
            if batch.processing_status == "ended":
                break
            elapsed = int(time.time() - start)
            counts = batch.request_counts
            print(f"  [{elapsed}s] status={batch.processing_status} "
                  f"succeeded={counts.succeeded} processing={counts.processing} "
                  f"errored={counts.errored} canceled={counts.canceled} expired={counts.expired}")
            time.sleep(self.poll_interval)

        results = {}
        errors = {}
        for r in self.client.messages.batches.results(batch_id):
            cid = r.custom_id
            if r.result.type == "succeeded":
                text = "".join(
                    block.text for block in r.result.message.content
                    if getattr(block, "type", None) == "text"
                )
                results[cid] = text
            else:
                err_info = getattr(r.result, "error", None) or r.result.type
                errors[cid] = str(err_info)

        if errors:
            print(f"  WARNING: {len(errors)} request(s) failed:")
            for cid, err in errors.items():
                print(f"    - {cid}: {err}")

        print(f"  Batch complete: {len(results)} succeeded, {len(errors)} failed")
        return results
