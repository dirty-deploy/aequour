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
    "Rules: keep every rupee amount exactly as written and keep every line item; mention depreciation where the "
    "original does; do not add any number, discount, promise, or part that is not in the original; do not say "
    "anything about limits, maximums or negotiation; plain friendly English, short paragraphs, no markdown.")

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


def parse_quote_json(raw):
    """Strict parse + type clean-up. Anything malformed becomes an empty quote (the engine then moves nothing)."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {"lines": [], "gst_percent": None, "grand_total": None, "parse_error": "no json"}
    try:
        q = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"lines": [], "gst_percent": None, "grand_total": None, "parse_error": str(e)}

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
    return {"lines": lines, "gst_percent": q.get("gst_percent"), "grand_total": num(q.get("grand_total"))}
