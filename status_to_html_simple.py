#!/usr/bin/env python3
"""
status_to_html.py

Parses raw health-check text and produces an HTML report with EXACTLY 2 server tiles per row.
Run: python status_to_html.py input.txt status_report.html
"""

import re, sys
from html import escape
from datetime import datetime

# ---------------------------
# Parser
# ---------------------------
def parse_group_by_env(lines):
    date = None
    env_map = {}
    current = None

    re_hdr = re.compile(r'Status of services on\s+([\d\.]+)(?:/([A-Za-z0-9_\-]+))?.*', re.I)
    re_fs_pct = re.compile(r'^\s*(\d{1,3})\s*%\s+(.+)$')
    re_fs_alt = re.compile(r'^\s*(.+?)\s*(?:==|=)\s*(\d{1,3})\s*%?\s*$')
    re_svc = re.compile(r'^\s*([^\s].*?)\s+is\s+([A-Za-z]+)(?:\s*#\s*(\d+))?', re.I)
    re_date = re.compile(r'generated at\s*(.+)', re.I)

    for ln in lines:
        s = ln.rstrip("\n")
        if not s.strip():
            continue

        # date
        mdate = re_date.search(s)
        if mdate and not date:
            date = mdate.group(1).strip()
            continue

        # header
        mh = re_hdr.search(s)
        if mh:
            ip = mh.group(1)
            host = mh.group(2) or ip
            env = host.split('-')[-1].upper() if '-' in host else (host.upper() if host else "GLOBAL")
            current = {"ip": ip, "host": host, "env": env, "files": [], "services": []}
            env_map.setdefault(env, []).append(current)
            continue

        if current is None:
            continue

        # fs pattern 1: "98% /path"
        mfs = re_fs_pct.match(s)
        if mfs:
            try:
                pct = int(mfs.group(1))
            except:
                pct = None
            name = mfs.group(2).strip()
            current["files"].append((name, pct, s.strip()))
            continue

        # fs alt
        mfs2 = re_fs_alt.match(s)
        if mfs2:
            a = mfs2.group(1).strip()
            b = mfs2.group(2).strip()
            if re.search(r'\d', b) and not re.search(r'\d', a):
                try:
                    pct = int(re.search(r'\d{1,3}', b).group(0))
                except:
                    pct = None
                name = a
            else:
                try:
                    pct = int(re.search(r'\d{1,3}', a).group(0))
                except:
                    pct = None
                name = b
            current["files"].append((name, pct, s.strip()))
            continue

        # service lines
        msvc = re_svc.match(s)
        if msvc:
            name = msvc.group(1).strip()
            status = msvc.group(2).strip()
            pid = msvc.group(3) or ""
            # store raw line but we will NOT show pid in the summary - expansion will show raw
            current["services"].append((name, status, pid, s.strip()))
            continue

    if not date:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return date, env_map

# ---------------------------
# Helpers
# ---------------------------
def color_for_pct(pct):
    if pct is None:
        return "#999"
    try:
        p = float(pct)
    except:
        return "#999"
    if p <= 60:
        return "#2ecc71"
    if p <= 80:
        return "#f39c12"
    return "#e74c3c"

def overall_status_for_services(services):
    if not services:
        return "No services"
    ok_words = ("run", "up", "active")
    for _, status, _, _ in services:
        if not status:
            return "Degraded"
        s = status.lower()
        if not any(w in s for w in ok_words):
            return "Degraded"
    return "Running"

# ---------------------------
# HTML Builder
# ---------------------------
def make_html_by_env(title, date, env_map):
    esc = escape
    head = "<!doctype html><html><head><meta charset='utf-8'><title>{}</title>".format(esc(title))
    head += "<style>"
    head += """
    *{box-sizing:border-box}
    body{font-family:Arial,Helvetica,sans-serif;background:#f4f6f8;margin:12px;color:#222}
    .container{max-width:1400px;margin:0 auto}
    .banner{background:#4caf50;color:#fff;padding:10px;border-radius:6px;font-weight:700;margin-bottom:12px}
    .env-title{font-size:16px;margin:18px 0 8px}
    /* FORCE exactly 2 columns per row (strong rule) */
    .server-grid{display:grid !important; grid-template-columns: repeat(2, 1fr) !important; gap:14px !important; align-items:start}
    .server-card{background:#fff;border-radius:8px;padding:12px;border:1px solid #e6e6e6; width:100%}
    .srv-meta{font-size:13px;color:#333;margin-bottom:8px}
    .files-table, .svc-full table{width:100%;border-collapse:collapse}
    .files-table td, .files-table th, .svc-full td, .svc-full th{padding:6px;border-bottom:1px solid #eee}
    .files-name{width:60%}
    .files-usage{width:40%;text-align:right}
    .usage-bar{display:inline-block;height:12px;width:160px;background:#eee;border-radius:8px;overflow:hidden;vertical-align:middle;margin-left:8px}
    .usage-fill{height:100%;display:block}
    .badge-running{background:#2ecc71;color:#fff;padding:6px 10px;border-radius:12px;font-weight:700}
    .badge-degraded{background:#f39c12;color:#fff;padding:6px 10px;border-radius:12px;font-weight:700}
    .badge-none{background:#7f8c8d;color:#fff;padding:6px 10px;border-radius:12px;font-weight:700}
    details.svc-block{margin-top:8px;padding:6px;background:#fff;border-radius:6px;border:1px solid #f0f0f0}
    details.svc-block summary{list-style:none;cursor:pointer;display:block}
    details.svc-block summary::-webkit-details-marker{display:none}
    .svc-summary{display:flex;gap:8px;align-items:center;white-space:nowrap}
    .svc-summary .host-name{font-weight:700;margin-right:8px}
    .svc-summary .hint{margin-left:auto;color:#666;font-size:12px}
    .svc-full{margin-top:8px}
    .svc-full pre{background:#fafafa;padding:8px;border-radius:4px;border:1px solid #eee;white-space:pre-wrap}
    """
    head += "</style></head><body>"
    head += "<div class='container'>"
    head += "<div class='banner'>{} <small style='font-weight:400;margin-left:12px'>Reported: {}</small></div>".format(esc(title), esc(date))

    # sort envs with GLOBAL last
    env_keys = sorted(env_map.keys(), key=lambda x: (x == "GLOBAL", x))
    for env in env_keys:
        servers = env_map.get(env, [])
        head += "<div><h2 class='env-title'>{} ({} servers)</h2>".format(esc(env), len(servers))
        head += "<div class='server-grid'>"
        for srv in servers:
            head += "<div class='server-card'>"

            # meta
            head += "<div class='srv-meta'><span style='font-size:14px;font-weight:700'>{}</span><br>IP: {}<br>Env: {}</div>".format(
                esc(srv.get("host","")), esc(srv.get("ip","")), esc(srv.get("env",""))
            )

            # filesystems
            files = srv.get("files", [])
            head += "<div><strong>Filesystems</strong>"
            if not files:
                head += "<div style='color:#666;margin-top:6px'>No filesystem lines found</div>"
            else:
                head += "<table class='files-table' style='margin-top:6px'>"
                head += "<tr><th class='files-name'>Name</th><th class='files-usage'>Usage</th></tr>"
                for name, pct, raw in files:
                    pct_val = pct if pct is not None else 0
                    col = color_for_pct(pct)
                    w = "{}%".format(max(0, min(100, pct_val)))
                    head += "<tr><td class='files-name'>{}</td><td class='files-usage'>{} <span class='usage-bar'><span class='usage-fill' style='width:{};background:{}'></span></span></td></tr>".format(
                        esc(name), esc(str(pct) + "%" if pct is not None else "N/A"), w, col
                    )
                head += "</table>"
            head += "</div>"

            # services summary + collapse
            services = srv.get("services", [])
            overall = overall_status_for_services(services)
            if overall == "Running":
                overall_badge = "<span class='badge-running'>Running</span>"
            elif overall == "No services":
                overall_badge = "<span class='badge-none'>No services</span>"
            else:
                overall_badge = "<span class='badge-degraded'>Degraded</span>"

            head += "<div style='margin-top:10px'><strong>Services</strong>"
            head += "<details class='svc-block'><summary><div class='svc-summary'>"
            # Show only host + overall badge in summary (no PID, no full svc list)
            head += "<span class='host-name'>{}</span> {}".format(esc(srv.get("host","")), overall_badge)
            head += "<span class='hint'>click to view complete status</span>"
            head += "</div></summary>"

            # expanded: table of services (no PID column)
            head += "<div class='svc-full'><table>"
            head += "<tr><th style='text-align:left'>Service</th><th style='text-align:right'>Status</th></tr>"
            for name, status, pid, raw in services:
                st = (status or "").strip()
                s_lower = st.lower()
                cls = "badge-running" if ("run" in s_lower or "up" in s_lower or "active" in s_lower) else "badge-degraded"
                # show service name and only the status (pid is purposely not printed in the table)
                head += "<tr><td>{}</td><td style='text-align:right'><span class='{}'>{}</span></td></tr>".format(esc(name), cls, esc(st))
            head += "</table>"

            # raw lines section (if present)
            if any(raw and raw.strip() for (_,_,_,raw) in services):
                head += "<div style='margin-top:8px;color:#666'><em>Raw lines:</em><pre>"
                for name, status, pid, raw in services:
                    if raw and raw.strip():
                        head += esc(raw) + "\n"
                head += "</pre></div>"

            head += "</div></details></div>"  # close details + services

            head += "</div>"  # close server-card

        head += "</div>"  # close server-grid
        head += "</div>"  # close env

    head += "</div></body></html>"
    return head

# ---------------------------
# Main
# ---------------------------
def main():
    if len(sys.argv) < 3:
        print("Usage: python status_to_html.py input.txt status_report.html")
        return
    infile = sys.argv[1]
    outfile = sys.argv[2]
    with open(infile, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    date, env_map = parse_group_by_env(lines)

    # DEBUG: print counts to terminal so you can confirm parser picked many servers
    print("DEBUG date:", date)
    print("DEBUG env counts:", {k: len(v) for k, v in env_map.items()})

    html = make_html_by_env("Environment health check report", date, env_map)
    with open(outfile, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Wrote:", outfile, "environments:", len(env_map))

if __name__ == "__main__":
    main()
