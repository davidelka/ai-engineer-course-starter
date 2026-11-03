"""Generate the binary documents of the Acme corpus (2 PDFs + 1 DOCX) and their sidecar metadata.

    pip install reportlab python-docx   # see ../requirements.txt
    python3 data/acme/corpus/build/make_binary_docs.py

The PDFs deliberately carry a running header and footer (with page numbers) and a table,
so that the ingestion lesson has boilerplate to strip and a table to keep intact.
"""
from __future__ import annotations

from pathlib import Path

import yaml

DOCS = Path(__file__).resolve().parents[1] / "docs"

# ---------------------------------------------------------------- content

SLA_2026 = {
    "meta": {"id": "sales-sla-2026", "title": "Acme Flow Service Level Agreement (2026)",
             "department": "sales_support", "doc_type": "contract_terms", "version": "2.0",
             "effective_date": "2026-01-01", "owner": "Shira Levin", "classification": "public",
             "language": "en", "supersedes": "sales-sla-2025", "format": "pdf", "file": "sales-sla-2026.pdf"},
    "header": "Acme Ltd.  |  Acme Flow Service Level Agreement  |  Version 2.0",
    "footer": "Public  -  Effective January 1, 2026",
    "blocks": [
        ("h1", "Acme Flow Service Level Agreement (2026)"),
        ("p", "This Service Level Agreement (\"SLA\") applies to customers on the Business and Enterprise plans from January 1, 2026. It replaces the 2025 SLA. Starter and Team plans are provided without an uptime commitment."),
        ("h2", "1. Uptime commitment"),
        ("p", "Acme will make the Acme Flow service available at least 99.9% of the time in each calendar month for Business customers, and at least 99.95% of the time in each calendar month for Enterprise customers."),
        ("p", "\"Available\" means that the public API and the web application respond successfully to requests, measured every minute from at least three external locations. A minute counts as unavailable when more than 5% of requests fail with server errors. Monthly uptime is the percentage of available minutes in the calendar month."),
        ("p", "For example, a 30-day month has 43,200 minutes. A commitment of 99.95% allows about 21.6 minutes of unavailability in such a month, and a commitment of 99.9% allows about 43.2 minutes."),
        ("h2", "2. Service credits"),
        ("p", "If monthly uptime falls below the commitment, the customer is entitled to a credit on the monthly fee of the affected plan, according to the following table:"),
        ("table", [["Plan", "Monthly uptime", "Credit"],
                   ["Enterprise", "below 99.95% but at least 99.5%", "10%"],
                   ["Enterprise", "below 99.5% but at least 99.0%", "20%"],
                   ["Enterprise", "below 99.0%", "30%"],
                   ["Business", "below 99.9% but at least 99.0%", "10%"],
                   ["Business", "below 99.0%", "25%"]]),
        ("p", "The maximum credit for a month is 30% of the monthly fee for Enterprise customers and 25% of the monthly fee for Business customers."),
        ("h2", "3. Requesting credits"),
        ("p", "Customers must request credits through Customer Support within 30 days after the end of the affected month. Acme may also issue credits proactively after a major incident. Credits are applied to the next invoice and are not paid out in cash."),
        ("h2", "4. Scheduled maintenance"),
        ("p", "Scheduled maintenance takes place in the weekly maintenance window, Sunday 02:00 to 06:00 UTC, and is announced at least 72 hours in advance on the status page. Scheduled maintenance of up to 4 hours per month does not count as unavailability."),
        ("h2", "5. Exclusions"),
        ("p", "Unavailability does not count against uptime when it is caused by third-party services outside Acme's control (including connected third-party tools), by the customer's own actions or configuration, by suspension of the account for non-payment or abuse, or by force majeure."),
        ("h2", "6. Sole remedy"),
        ("p", "Service credits are the customer's sole and exclusive remedy for failure to meet the uptime commitment, unless the customer's Enterprise agreement states otherwise."),
        ("h2", "7. Changes from the 2025 SLA"),
        ("p", "The Enterprise uptime commitment increased from 99.9% to 99.95%, Enterprise credits now have three levels (10%, 20% and 30%), and the maximum Enterprise credit increased from 25% to 30%. The Business commitment and credits are unchanged."),
    ],
}

TRAVEL_2026 = {
    "meta": {"id": "fin-travel-2026", "title": "Travel Policy (2026)", "department": "finance",
             "doc_type": "policy", "version": "2.0", "effective_date": "2026-02-01", "owner": "Keren Amar",
             "classification": "internal", "language": "en", "supersedes": "fin-travel-2025",
             "format": "pdf", "file": "fin-travel-2026.pdf"},
    "header": "Acme Ltd.  |  Finance  |  Travel Policy v2.0",
    "footer": "Internal  -  Effective February 1, 2026  -  Owner: Keren Amar",
    "blocks": [
        ("h1", "Travel Policy (effective February 2026)"),
        ("p", "This policy replaces the January 2025 Travel Policy. It covers business travel abroad and domestic travel between Acme offices, for employees and for contractors traveling on Acme's behalf. The per diem rates and hotel caps were raised to reflect higher prices in 2025."),
        ("h2", "1. Approval and booking"),
        ("p", "Every trip abroad needs the approval of the department VP before booking. Trips are booked through TripDesk. Bookings made elsewhere are reimbursed only if they were cheaper than the TripDesk offer at the time of booking."),
        ("h2", "2. Flights"),
        ("p", "Economy class is the default. On flights longer than 6 hours, all employees may book premium economy. VP-level employees and above may fly business class on flights longer than 8 hours. Book at least 14 days in advance when possible."),
        ("h2", "3. Hotels"),
        ("p", "Hotel caps per night: up to $210 in standard cities and up to $300 in high-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo)."),
        ("p", "Berlin office visits: employees must stay in the Acme corporate apartment when it is available. When it is not available, the hotel cap in Berlin is 170 EUR per night."),
        ("h2", "4. Per diem"),
        ("p", "The per diem covers meals, local transport within the city, and small expenses. It is paid with the salary after the trip, based on the number of days abroad, according to this table:"),
        ("table", [["Destination", "Per diem per day"],
                   ["Standard cities", "$85"],
                   ["High-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo)", "$110"],
                   ["Berlin office visits", "65 EUR"]]),
        ("p", "The day of departure and the day of return count as full days when the flight leaves before 12:00 or lands after 18:00 local time; otherwise they count as half days. When meals are provided by a conference or a customer, the per diem for that day is reduced by 30%."),
        ("h2", "5. Domestic travel"),
        ("p", "Trips between Tel Aviv and Haifa: the train is preferred. Private car use is reimbursed per the Business Expenses Policy. Overnight stays in Haifa for workshops: up to 650 NIS per night."),
        ("h2", "6. Insurance and safety"),
        ("p", "Travel health insurance is purchased centrally by Acme for every approved trip. Travelers to countries on the Security team's high-risk list must request a loaner laptop from IT at least 5 working days before the trip."),
        ("h2", "7. Summary of changes from 2025"),
        ("p", "Per diem increased from $75 to $85 in standard cities and from $95 to $110 in high-cost cities. Hotel caps increased from $180 to $210 (standard) and from $260 to $300 (high-cost). Premium economy is new for flights over 6 hours, business class for VPs now starts at 8 hours instead of 10, and Tokyo was added to the high-cost list."),
    ],
}

RELOCATION = {
    "meta": {"id": "hr-relocation", "title": "Relocation Policy", "department": "hr", "doc_type": "policy",
             "version": "1.1", "effective_date": "2025-10-01", "owner": "Orly Peretz",
             "classification": "confidential", "language": "en", "format": "docx", "file": "hr-relocation.docx"},
    "header": "Acme Ltd. - People Team - Confidential",
    "footer": "Relocation Policy v1.1 - effective October 1, 2025",
    "blocks": [
        ("h1", "Relocation Policy"),
        ("p", "This policy describes the support Acme provides when an employee moves between Acme offices at the company's request or with the company's approval: between Israel and Berlin, or between Haifa and Tel Aviv. It also applies to new hires who relocate to join Acme, when agreed in the offer letter."),
        ("h2", "Eligibility and approval"),
        ("p", "A relocation must be approved by the department VP and the VP People before the employee commits to the move. Internal transfers are open to employees with at least 12 months at Acme. Relocation is never mandatory."),
        ("h2", "Relocation packages"),
        ("p", "The package depends on the type of move:"),
        ("table", [["Move", "Lump sum", "Temporary housing", "Flights"],
                   ["Israel to Berlin", "8,000 EUR", "up to 30 nights", "economy, employee and immediate family"],
                   ["Berlin to Israel", "30,000 NIS", "up to 30 nights", "economy, employee and immediate family"],
                   ["Haifa to Tel Aviv or Tel Aviv to Haifa", "10,000 NIS", "up to 14 nights", "not applicable"]]),
        ("p", "The lump sum is paid with the first salary after the move and is subject to tax. It is meant to cover shipping, furniture, deposits and other moving costs at the employee's discretion."),
        ("h2", "Visa and work permit"),
        ("p", "For moves to Berlin, Acme's relocation partner handles the work permit application (usually the EU Blue Card) and the city registration (Anmeldung). Acme pays all fees. Employees should plan for 8 to 12 weeks from the start of the process to the permit."),
        ("h2", "Language and settling in"),
        ("p", "Employees moving to Berlin can take a German course paid by Acme, up to 1,500 EUR in the first year. Acme also pays for one consultation with a tax advisor in each country in the year of the move."),
        ("h2", "Repayment"),
        ("p", "An employee who leaves Acme voluntarily within 12 months of the move repays 100% of the lump sum; between 12 and 24 months after the move, 50%. No repayment is required if Acme ends the employment for reasons other than misconduct."),
        ("h2", "Contact"),
        ("p", "Relocation questions go to Sivan Elbaz (HR Manager). For Berlin-specific matters, Katrin Vogel coordinates with the relocation partner."),
    ],
}


# ---------------------------------------------------------------- writers

def make_pdf(spec: dict) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path = DOCS / spec["meta"]["file"]
    styles = getSampleStyleSheet()
    story = []
    cell = styles["BodyText"]
    for kind, val in spec["blocks"]:
        if kind == "h1":
            story += [Paragraph(val, styles["Title"]), Spacer(1, 6)]
        elif kind == "h2":
            story.append(Paragraph(val, styles["Heading2"]))
        elif kind == "p":
            story += [Paragraph(val.replace("&", "&amp;"), styles["BodyText"]), Spacer(1, 4)]
        elif kind == "table":
            data = [[Paragraph(c, cell) for c in row] for row in val]
            widths = [6 * cm, 6.5 * cm, 3.5 * cm] if len(val[0]) == 3 else [11 * cm, 5 * cm]
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde4f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [t, Spacer(1, 8)]

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, spec["header"])
        canvas.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
        canvas.drawString(2 * cm, 1.2 * cm, spec["footer"])
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
                            title=spec["meta"]["title"], author=spec["meta"]["owner"])
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def make_docx(spec: dict) -> None:
    from docx import Document

    d = Document()
    sec = d.sections[0]
    sec.header.paragraphs[0].text = spec["header"]
    sec.footer.paragraphs[0].text = spec["footer"]
    d.core_properties.title = spec["meta"]["title"]
    d.core_properties.author = spec["meta"]["owner"]
    for kind, val in spec["blocks"]:
        if kind == "h1":
            d.add_heading(val, level=1)
        elif kind == "h2":
            d.add_heading(val, level=2)
        elif kind == "p":
            d.add_paragraph(val)
        elif kind == "table":
            t = d.add_table(rows=len(val), cols=len(val[0]))
            t.style = "Table Grid"
            for i, row in enumerate(val):
                for j, c in enumerate(row):
                    t.cell(i, j).text = c
    d.save(DOCS / spec["meta"]["file"])


def write_meta(spec: dict) -> None:
    meta = spec["meta"]
    with open(DOCS / f"{meta['id']}.meta.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    for spec in (SLA_2026, TRAVEL_2026):
        make_pdf(spec)
        write_meta(spec)
    make_docx(RELOCATION)
    write_meta(RELOCATION)
    print("ok")
