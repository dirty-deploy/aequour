"""
Qwen3-VL language layer. Three jobs only; it never sets, sees or edits a price limit.

  reword(rationale)      rephrase the engine's customer rationale  -> ALWAYS passed through rationale.safe_reply()
  read_quote(image)      read line items off a garage quote photo   -> quote JSON for dispute.check_quote()
  read_plate(crop)       read the number plate from a crop          -> string, compared with the policy plate in code

Checkpoint: Qwen/Qwen3-VL-8B-Instruct (8B parameters), loaded 4-bit NF4 with bitsandbytes, bf16 compute.
Inputs the model is allowed to receive: build_rationale() text (no ceiling), images. NEVER res["ceiling"],
res["ceiling_lines"] or engine.pivots() output (guarded in reword()).
"""
import json
import re
import time

MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"

REWORD_SYSTEM = (
    "You rewrite a motor-insurance settlement explanation so a customer understands it. "
    "Keep this shape: the answer first (Your offer is ...), then one short line saying what was found, then one bullet per "
    "cost component, then the total line, then the assumptions. Keep every rupee amount exactly as written and keep every line "
    "item and every depreciation line. Use short sentences and everyday words, one idea per line, a blank line between blocks. "
    "Warm but direct, with at most one friendly sentence. Do not add any number, discount, promise, or part that is not in the "
    "original. Do not say anything about limits, maximums or negotiation. Do not write approved or guaranteed. "
    "Do not write a Next step line: the system adds it. Plain English, no markdown other than the leading hyphen bullets.")

QUOTE_SYSTEM = (
    "You read a garage repair estimate image and return JSON only, no prose. Schema: "
    '{"lines":[{"description":str,"type":"part"|"labour"|"paint","qty":int,"unit_price":int,"total":int}],'
    '"gst_percent":number|null,"grand_total":int|null}. '
    "Copy descriptions as written. Amounts in rupees as integers without commas. Painting/denting work is 'paint', "
    "fitting/removal/labour charges are 'labour', anything bought is 'part'. If a value is unreadable use null.")

PLATE_PROMPT = ("Read the vehicle registration number on this number plate. Reply with the characters only "
                "(for example DL3CAB1234), or NONE if it is not readable.")

INDIAN_PLATE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{3,4}$|^\d{2}BH\d{4}[A-Z]{1,2}$")


class QwenVL:
    def __init__(self, model_id=MODEL_ID, four_bit=True):
        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration
        t0 = time.time()
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.bfloat16) if four_bit else None
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_id, quantization_config=q, dtype=torch.bfloat16, device_map="cuda:0")
        # cap image tokens so an 8 GB card does not run out of memory on phone photos
        self.processor = AutoProcessor.from_pretrained(model_id, min_pixels=256 * 28 * 28, max_pixels=768 * 28 * 28)
        self.model_id, self.load_s = model_id, round(time.time() - t0, 1)
        self.vram_gb = round(torch.cuda.max_memory_allocated() / 1e9, 2)

    # ------------------------------------------------------------------ core call
    def chat(self, messages, max_new_tokens=512):
        import torch
        inputs = self.processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                    return_dict=True, return_tensors="pt").to(self.model.device)
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return text.strip()

    @staticmethod
    def _pil(img):
        from PIL import Image
        if isinstance(img, Image.Image):
            return img
        if isinstance(img, str):
            return Image.open(img).convert("RGB")
        import cv2
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))   # numpy BGR from OpenCV

    # ------------------------------------------------------------------ jobs
    def reword(self, rationale_text, result=None):
        if result is not None:
            # guard: the ceiling must not be anywhere in what we send
            ceil = result.get("ceiling")
            if ceil and ceil != result.get("offer") and str(ceil) in re.sub(r"[,\s]", "", rationale_text):
                raise ValueError("refusing to send text containing the ceiling to the model")
        msgs = [{"role": "system", "content": [{"type": "text", "text": REWORD_SYSTEM}]},
                {"role": "user", "content": [{"type": "text", "text": rationale_text}]}]
        return self.chat(msgs, max_new_tokens=700)

    def read_quote(self, image):
        msgs = [{"role": "system", "content": [{"type": "text", "text": QUOTE_SYSTEM}]},
                {"role": "user", "content": [{"type": "image", "image": self._pil(image)},
                                             {"type": "text", "text": "Return the JSON for this estimate."}]}]
        raw = self.chat(msgs, max_new_tokens=900)
        return parse_quote_json(raw), raw

    def read_plate(self, crop):
        msgs = [{"role": "user", "content": [{"type": "image", "image": self._pil(crop)},
                                             {"type": "text", "text": PLATE_PROMPT}]}]
        raw = re.sub(r"[^A-Z0-9]", "", self.chat(msgs, max_new_tokens=20).upper())
        return raw if raw and raw != "NONE" and INDIAN_PLATE.match(raw) else None


def repair_json(text):
    """Close brackets or braces a model dropped (e.g. a missing ']' before "gst_percent"). Returns the repaired
    text, or None when the text cannot be fixed safely (cut off inside a string, wrong nesting, no JSON start).
    It only adds closers and never invents or changes a value; the caller validates the result with json.loads."""
    start = (text or "").find("{")
    if start < 0:
        return None
    s, out, stack, in_str, esc = re.sub(r"\s*`{3}\s*$", "", text[start:]), [], [], False, False
    for i, ch in enumerate(s):
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            if stack and stack[-1] == "[" and re.match(r'"[A-Za-z_]+"\s*:', s[i:]):
                # an object key where an array element belongs: the array was never closed
                while out and out[-1] in " \t\r\n,":
                    out.pop()
                out.append("],")
                stack.pop()
            in_str = True
            out.append(ch)
        elif ch in "{[":
            stack.append(ch)
            out.append(ch)
        elif ch in "}]":
            want = "{" if ch == "}" else "["
            if not stack:
                return None
            if stack[-1] != want:
                if stack[-1] == "[" and ch == "}" or stack[-1] == "{" and ch == "]":
                    while out and out[-1] in " \t\r\n,":
                        out.pop()
                    out.append("]" if stack[-1] == "[" else "}")
                    stack.pop()
                    if not stack or stack[-1] != want:
                        return None
                else:
                    return None
            stack.pop()
            out.append(ch)
            if not stack:
                break                                   # root object closed; ignore trailing text such as a code fence
        else:
            out.append(ch)
    if in_str:
        return None
    while out and out[-1] in " \t\r\n,":
        out.pop()
    tail = "".join(out)
    # cut off mid-value inside a line item (a number half written) is not safe to close; at the root level the last
    # value is only gst_percent / grand_total, which never set a payment
    if stack and not (tail[-1:] in '}]"' or (stack == ["{"] and (tail[-1:].isdigit() or tail.endswith("null")))):
        return None
    return tail + "".join("}" if b == "{" else "]" for b in reversed(stack))


def parse_quote_json(raw):
    """Strict parse + type clean-up. A reply with a missing closing bracket or brace is repaired (repair_json) and
    then goes through exactly the same clean-up and checks. Anything else malformed becomes an empty quote
    (the engine then moves nothing)."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    repaired = False
    try:
        if not m:
            raise json.JSONDecodeError("no json", raw or "", 0)
        q = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        fixed = repair_json(raw)
        try:
            q = json.loads(fixed) if fixed else None
        except json.JSONDecodeError:
            q = None
        if not isinstance(q, dict):
            return {"lines": [], "gst_percent": None, "grand_total": None,
                    "parse_error": "no json" if not m and "{" not in (raw or "") else str(e)}
        repaired = True

    def num(x):
        if x is None:
            return None
        try:
            return int(round(float(str(x).replace(",", "").replace("₹", "").strip())))
        except ValueError:
            return None

    lines = []
    for ln in q.get("lines") or []:
        t = str(ln.get("type", "")).lower()
        t = t if t in ("part", "labour", "paint") else "other"
        qty = num(ln.get("qty")) or 1
        unit, total = num(ln.get("unit_price")), num(ln.get("total"))
        if unit is None and total is not None:
            unit = total // max(qty, 1)
        if total is None and unit is not None:
            total = unit * qty
        if unit is None:
            continue
        lines.append({"description": str(ln.get("description", ""))[:80], "type": t, "qty": qty,
                      "unit_price": unit, "total": total})
    out = {"lines": lines, "gst_percent": q.get("gst_percent"), "grand_total": num(q.get("grand_total"))}
    if repaired:
        out["repaired"] = True      # audit marker only; the dispute checker ignores it
    return out
