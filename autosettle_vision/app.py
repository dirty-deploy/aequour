"""
Auto-Settle AI demo web app (local).   python -m autosettle_vision.app [--no-qwen] [--port 7860]

Flow: pick policy (simulated plate lookup) -> upload photos or a walk-around video -> assess -> offer with itemised
rationale -> optional garage quote (photo) -> line-by-line check -> accept / partner garage / surveyor.
Every step is written to the hash-chained audit log shown on the last tab.
"""
import argparse
import json

import cv2
import gradio as gr
import numpy as np

from autosettle_engine import engine as E, rationale as R
from autosettle_engine.dispute import ClaimSession

from . import pipeline as P
from .claim import POLICIES, RC, customer_text, engine_vision, get_policy

QWEN = None
COLORS = {"Dent": (0, 140, 255), "Broken part": (0, 0, 230), "Missing part": (200, 0, 200), "Surface damage": (0, 200, 200)}


def annotate(path, per_image_findings):
    img = cv2.imread(path)
    for f in per_image_findings:
        if f.get("part_polygon"):
            cv2.polylines(img, [np.asarray(f["part_polygon"], np.int32)], True, (255, 255, 255), 2)
        c = COLORS.get(f["damage_class"], (0, 255, 0))
        if f.get("damage_box"):
            x1, y1, x2, y2 = map(int, f["damage_box"])
            cv2.rectangle(img, (x1, y1), (x2, y2), c, 3)
            label = f"{f['part_class']} | {f['damage_class']} | {f['severity'] or '?'} {f['damage_conf']:.2f}"
            cv2.putText(img, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
        elif f.get("damage_polygon"):
            cv2.polylines(img, [np.asarray(f["damage_polygon"], np.int32)], True, c, 3)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def assess(policy_id, files, video, st):
    pol = get_policy(policy_id)
    paths = [f if isinstance(f, str) else f.name for f in (files or [])]
    if not paths and not video:
        return st, None, "Upload photos or a video first.", "", "", gr.update(visible=False)
    reader = QWEN.read_plate if QWEN else None
    v = P.run_claim(paths, video, plate_reader=reader)
    ev = engine_vision(v)
    s = ClaimSession(pol, RC)
    res = s.submit(ev)
    text, used, viol = customer_text(res, pol, ev, QWEN)
    s._log("customer_message", {"model_wording_used": used, "violations": [str(x) for x in viol]})
    gallery = []
    for pth in paths:
        name = pth.replace("\\", "/").split("/")[-1]
        fs = v["findings_by_image"].get(name, [])
        gallery.append((annotate(pth, fs), name))
    rows = "\n".join(f"| {d['part_class']} | {d['damage_class']} | {d['severity']} | {d['damage_area_fraction']} | "
                     f"{d['damage_conf']} | {d.get('damage_source', '')} |" for d in v["detections"])
    plate = v["plate_read"] or "not read"
    match = "matches policy" if v["plate_read"] and E.norm_plate(v["plate_read"]) == E.norm_plate(pol.plate) else "NOT verified"
    summary = (f"**Decision: {res['decision']}**" + (f" — offer **{R.money(res['offer'])}**" if res["offer"] is not None else "")
               + f"\n\nPlate read: `{plate}` ({match}) · information completeness {res['tci']}"
               + (f"\n\nReasons: {', '.join(res['reasons'])}" if res["reasons"] else "")
               + (f"\n\nMissing: {', '.join(res['missing'])}" if res["missing"] else "")
               + (f"\n\nIntegrity flags: {', '.join(v['integrity_flags'])}" if v["integrity_flags"] else "")
               + "\n\n| Part | Damage | Severity | Area | Conf | Source |\n|---|---|---|---|---|---|\n" + rows)
    src = "Qwen3-VL wording (passed all checks)" if used else (
        "Fixed template" + (f" (Qwen wording blocked: {', '.join(k for k, _ in viol)})" if viol else ""))
    st = {"session": s, "vision": ev}
    return st, gallery, summary, f"*{src}*\n\n" + text.replace("\n", "\n\n"), audit_md(s), gr.update(visible=res["decision"] == "OFFER")


def read_quote(qimg, qjson, st):
    if not st or st["session"].state not in ("OFFERED", "UPDATED_OFFER"):
        return "No open offer to dispute.", "", st and audit_md(st["session"])
    s = st["session"]
    if qimg is not None and QWEN is not None:
        quote, raw = QWEN.read_quote(qimg)
        s._log("quote_read_by_model", {"lines": len(quote["lines"])})
    else:
        try:
            quote = json.loads(qjson)
        except Exception:
            return "Upload a quote photo (needs Qwen) or paste quote JSON.", "", audit_md(s)
    chk = s.dispute(quote)
    rows = "\n".join(f"| {v['description']} | {R.money(v['quoted'])} | {v['verdict']} | {v.get('reason', '')} |" for v in chk["verdicts"])
    md = (f"Quote read: {len(quote.get('lines', []))} lines\n\n| Line | Quoted | Verdict | Why |\n|---|---|---|---|\n{rows}\n\n"
          f"**Offer {'updated to' if chk['moved'] else 'stays at'} {R.money(chk['updated_offer'])}** (was {R.money(chk['current_offer'])})."
          + (f"\n\n{chk['note']}" if chk.get("note") else "")
          + "\n\nYour options: accept the updated cash offer · repair at a partner garage at agreed rates · ask for a surveyor.")
    return md, json.dumps(quote, indent=1), audit_md(s)


def choose(option, st):
    if not st:
        return "Assess a claim first.", ""
    s = st["session"]
    try:
        if option == "accept" and s.state == "OFFERED":
            s.accept()
        else:
            s.choose({"accept": "accept_updated", "garage": "partner_garage", "surveyor": "surveyor"}[option])
    except AssertionError as e:
        return f"Not allowed: {e}", audit_md(s)
    return f"Claim closed: **{s.state}** at {R.money(s.current_offer) if s.current_offer else '-'}", audit_md(s)


def message(text, st):
    if not st:
        return "Assess a claim first.", ""
    s = st["session"]
    flags = s.message(text)
    reply = ("Your message has been passed to a claims specialist." if "abusive" in flags else
             "Thanks. Messages are recorded with the claim, but amounts change only with photos or an itemised quote.")
    return reply + (f"  _(flags: {', '.join(flags)})_" if flags else ""), audit_md(s)


def audit_md(s):
    ok = ClaimSession.verify_log(s.log)
    rows = "\n".join(f"| {r['seq']} | {r['event']} | {r['state']} | `{r['hash'][:12]}` |" for r in s.log)
    return f"Chain intact: **{ok}** · state **{s.state}**\n\n| # | Event | State | Hash |\n|---|---|---|---|\n{rows}"


def build():
    with gr.Blocks(title="Auto-Settle AI") as demo:
        st = gr.State(None)
        gr.Markdown("# Auto-Settle AI\nThe AI perceives and talks. Deterministic code decides every rupee.")
        with gr.Row():
            pol = gr.Dropdown([(f"{p['plate']} · {p['make']} {p['model']} ({p['reg_date'][:4]})", k) for k, p in POLICIES.items()],
                              value="POL-DEMO-001", label="Policy (simulated plate lookup)")
        with gr.Row():
            files = gr.File(file_count="multiple", file_types=["image"], label="Photos (start with the number plate)")
            video = gr.Video(label="…or a walk-around video")
        go = gr.Button("Assess claim", variant="primary")
        with gr.Tab("Assessment"):
            summary = gr.Markdown()
            gallery = gr.Gallery(label="What the models saw", columns=3, height=420)
        with gr.Tab("Customer message"):
            cust = gr.Markdown()
            msg = gr.Textbox(label="Customer reply (free text never changes an amount)")
            msg_out = gr.Markdown()
        with gr.Tab("Dispute with a garage quote") as dispute_tab:
            with gr.Row():
                qimg = gr.Image(type="pil", label="Garage quote photo (read by Qwen3-VL)")
                qjson = gr.Code(language="json", label="…or quote JSON")
            qbtn = gr.Button("Check quote")
            qout = gr.Markdown()
            with gr.Row():
                b1 = gr.Button("Accept cash offer")
                b2 = gr.Button("Partner garage")
                b3 = gr.Button("Ask for surveyor")
            close = gr.Markdown()
        with gr.Tab("Audit log"):
            audit = gr.Markdown()
        go.click(assess, [pol, files, video, st], [st, gallery, summary, cust, audit, dispute_tab])
        msg.submit(message, [msg, st], [msg_out, audit])
        qbtn.click(read_quote, [qimg, qjson, st], [qout, qjson, audit])
        b1.click(lambda s: choose("accept", s), [st], [close, audit])
        b2.click(lambda s: choose("garage", s), [st], [close, audit])
        b3.click(lambda s: choose("surveyor", s), [st], [close, audit])
    return demo


def main():
    global QWEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-qwen", action="store_true")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    if not a.no_qwen:
        from .qwen import QwenVL
        QWEN = QwenVL()
    build().launch(server_name="127.0.0.1", server_port=a.port)


if __name__ == "__main__":
    main()
