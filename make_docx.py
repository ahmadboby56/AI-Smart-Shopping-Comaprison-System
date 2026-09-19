import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
import os

def create_docx():
    doc = docx.Document()

    # Set Margins (Standard 0.75 in / 19 mm)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)

    # Styles
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Calibri'
    font.size = Pt(10)
    font.color.rgb = RGBColor(15, 23, 42)

    # Color Palette
    COLOR_NAVY = RGBColor(15, 23, 42)       # #0f172a
    COLOR_INDIGO = RGBColor(99, 102, 241)   # #6366f1
    COLOR_EMERALD = RGBColor(16, 185, 129)  # #10b981
    COLOR_DARK_TEXT = RGBColor(30, 41, 59)

    # Helper: Shading table cell
    def set_cell_background(cell, fill_hex):
        tcPr = cell._element.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    # Helper: Set Cell Margins
    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._element.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    # HEADER BANNER TABLE
    header_table = doc.add_table(rows=1, cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = header_table.cell(0, 0)
    cell.width = Inches(7.3)
    set_cell_background(cell, "0F172A")
    set_cell_margins(cell, top=180, bottom=180, left=200, right=200)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("🛒 Smart Shopping AI Engine")
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = RGBColor(255, 255, 255)

    p2 = cell.add_paragraph()
    p2.paragraph_format.space_before = Pt(0)
    p2.paragraph_format.space_after = Pt(4)
    run2 = p2.add_run("Multi-Source E-Commerce Aggregator & Voice AI Price Comparison Platform")
    run2.font.size = Pt(10)
    run2.font.color.rgb = RGBColor(199, 210, 254)

    p3 = cell.add_paragraph()
    p3.paragraph_format.space_before = Pt(4)
    p3.paragraph_format.space_after = Pt(0)
    run3 = p3.add_run("IISAT × InnoVista AI Summit ’26 | Shortlisted Project Submission")
    run3.font.size = Pt(9)
    run3.font.bold = True
    run3.font.color.rgb = RGBColor(129, 140, 248)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # EXECUTIVE SUMMARY BOX
    summary_table = doc.add_table(rows=1, cols=1)
    summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_s = summary_table.cell(0, 0)
    cell_s.width = Inches(7.3)
    set_cell_background(cell_s, "EFF6FF")
    set_cell_margins(cell_s, top=140, bottom=140, left=180, right=180)

    ps = cell_s.paragraphs[0]
    ps.paragraph_format.space_after = Pt(4)
    r = ps.add_run("📌 Executive Project Overview")
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = RGBColor(29, 78, 216)

    ps2 = cell_s.add_paragraph()
    ps2.paragraph_format.space_after = Pt(0)
    ps2.paragraph_format.line_spacing = 1.15
    r2 = ps2.add_run(
        "Smart Shopping is an intelligent full-stack e-commerce aggregation and voice-assisted decision engine. "
        "It unifies product listings across 10+ major online marketplaces (Daraz.pk, PriceOye, Telemart, Mega.pk, Ubuy, Amazon, eBay, etc.) in real time. "
        "Powered by multi-accent acoustic speech recognition, backend Levenshtein fuzzy string resolution, and TextBlob NLP sentiment analysis, "
        "Smart Shopping empowers users to discover transparent pricing, evaluate seller credibility, track historical price volatility, and save time & money."
    )
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = RGBColor(30, 64, 175)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # SECTION 1: CORE AI INNOVATIONS
    h1 = doc.add_paragraph()
    h1.paragraph_format.space_before = Pt(8)
    h1.paragraph_format.space_after = Pt(4)
    hr1 = h1.add_run("🚀 Core AI & Technical Innovations")
    hr1.font.size = Pt(12)
    hr1.font.bold = True
    hr1.font.color.rgb = COLOR_NAVY

    # Table of 3 Cards
    card_table = doc.add_table(rows=1, cols=3)
    card_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = [Inches(2.4), Inches(2.4), Inches(2.4)]

    # Col 1: Voice AI
    c1 = card_table.cell(0, 0)
    c1.width = widths[0]
    set_cell_background(c1, "F8FAFC")
    set_cell_margins(c1, top=100, bottom=100, left=120, right=120)
    p_c1 = c1.paragraphs[0]
    p_c1.paragraph_format.space_after = Pt(4)
    r_c1 = p_c1.add_run("🎙️ Multi-Accent Voice AI")
    r_c1.font.bold = True
    r_c1.font.size = Pt(10)
    r_c1.font.color.rgb = COLOR_INDIGO

    p_c1b = c1.add_paragraph()
    p_c1b.paragraph_format.space_after = Pt(0)
    p_c1b.paragraph_format.line_spacing = 1.1
    r_c1b = p_c1b.add_run(
        "Integrates Web Speech API with dynamic browser locale detection (navigator.language) and multi-alternative evaluation (maxAlternatives=5). "
        "Accurately transcribes South Asian, Middle Eastern, and Western English accents."
    )
    r_c1b.font.size = Pt(8.5)

    # Col 2: Levenshtein Fuzzy Search
    c2 = card_table.cell(0, 1)
    c2.width = widths[1]
    set_cell_background(c2, "F8FAFC")
    set_cell_margins(c2, top=100, bottom=100, left=120, right=120)
    p_c2 = c2.paragraphs[0]
    p_c2.paragraph_format.space_after = Pt(4)
    r_c2 = p_c2.add_run("🔤 Fuzzy Search Engine")
    r_c2.font.bold = True
    r_c2.font.size = Pt(10)
    r_c2.font.color.rgb = COLOR_EMERALD

    p_c2b = c2.add_paragraph()
    p_c2b.paragraph_format.space_after = Pt(0)
    p_c2b.paragraph_format.line_spacing = 1.1
    r_c2b = p_c2b.add_run(
        "Backend fault-tolerance powered by Python's difflib string distance. Automatically resolves voice transcription errors or phonetic typos "
        "(e.g., 'airburds' -> 'AirPods Pro'), eliminating zero-result search failures."
    )
    r_c2b.font.size = Pt(8.5)

    # Col 3: NLP Merchant Trust Rating
    c3 = card_table.cell(0, 2)
    c3.width = widths[2]
    set_cell_background(c3, "F8FAFC")
    set_cell_margins(c3, top=100, bottom=100, left=120, right=120)
    p_c3 = c3.paragraphs[0]
    p_c3.paragraph_format.space_after = Pt(4)
    r_c3 = p_c3.add_run("🛡️ NLP Trust Score Badge")
    r_c3.font.bold = True
    r_c3.font.size = Pt(10)
    r_c3.font.color.rgb = RGBColor(217, 119, 6)

    p_c3b = c3.add_paragraph()
    p_c3b.paragraph_format.space_after = Pt(0)
    p_c3b.paragraph_format.line_spacing = 1.1
    r_c3b = p_c3b.add_run(
        "Evaluates seller review sentiment via TextBlob NLP, price volatility ratios, warranty terms, and return rate metrics to compute an automated "
        "0–100 Trust Score badge per product listing."
    )
    r_c3b.font.size = Pt(8.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # SECTION 2: TECH STACK & MODULE MATRIX
    h2 = doc.add_paragraph()
    h2.paragraph_format.space_before = Pt(8)
    h2.paragraph_format.space_after = Pt(4)
    hr2 = h2.add_run("🛠️ Technology Specification Matrix")
    hr2.font.size = Pt(12)
    hr2.font.bold = True
    hr2.font.color.rgb = COLOR_NAVY

    matrix_table = doc.add_table(rows=6, cols=3)
    matrix_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Subsystem / Module", "Core Technology", "Functional Purpose"]
    data = [
        ["Web Backend & API", "Python 3.10, Flask 3.0, Gunicorn", "RESTful endpoints, session security, CORS proxying"],
        ["Voice Recognition", "Web Speech API, Locale Adaptation", "Hands-free voice querying with South Asian accent adaptation"],
        ["Multi-Source Scraper", "BeautifulSoup4, Requests, Threading", "Parallelized scraping of prices, images, ratings from 10+ sites"],
        ["NLP Sentiment Engine", "TextBlob NLP Library", "Polarity & subjectivity extraction to grade merchant credibility"],
        ["Data Storage & Analytics", "SQLite3, Chart.js", "Historical price logging, trend charts, volume analytics"]
    ]

    # Header Row Formatting
    hdr_cells = matrix_table.rows[0].cells
    for i, h_text in enumerate(headers):
        hdr_cells[i].text = h_text
        set_cell_background(hdr_cells[i], "F1F5F9")
        set_cell_margins(hdr_cells[i], top=80, bottom=80, left=100, right=100)
        p = hdr_cells[i].paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(9)
        p.runs[0].font.color.rgb = COLOR_NAVY

    # Data Rows Formatting
    for r_idx, row_data in enumerate(data):
        row_cells = matrix_table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=60, bottom=60, left=100, right=100)
            p = row_cells[c_idx].paragraphs[0]
            if len(p.runs) > 0:
                p.runs[0].font.size = Pt(8.5)
                if c_idx == 0:
                    p.runs[0].font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # PAGE BREAK FOR EXACT PAGE 2 SPLIT
    doc.add_page_break()

    # PAGE 2 HEADER
    h2_head = doc.add_paragraph()
    h2_head.paragraph_format.space_before = Pt(0)
    h2_head.paragraph_format.space_after = Pt(6)
    hr2_h = h2_head.add_run("🌐 Marketplace Coverage, Analytics & Business ROI")
    hr2_h.font.size = Pt(14)
    hr2_h.font.bold = True
    hr2_h.font.color.rgb = COLOR_NAVY

    # SECTION 3: MARKETPLACE & ANALYTICS
    grid2_table = doc.add_table(rows=1, cols=2)
    grid2_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    c_g1 = grid2_table.cell(0, 0)
    c_g1.width = Inches(3.6)
    set_cell_background(c_g1, "F8FAFC")
    set_cell_margins(c_g1, top=100, bottom=100, left=120, right=120)
    p_g1 = c_g1.paragraphs[0]
    p_g1.paragraph_format.space_after = Pt(4)
    r_g1 = p_g1.add_run("🛍️ 10+ E-Commerce Platforms")
    r_g1.font.bold = True
    r_g1.font.size = Pt(10)
    r_g1.font.color.rgb = COLOR_INDIGO

    p_g1b = c_g1.add_paragraph()
    p_g1b.paragraph_format.space_after = Pt(0)
    p_g1b.paragraph_format.line_spacing = 1.15
    r_g1b = p_g1b.add_run(
        "Scrapes and aggregates live product listings from Daraz.pk, PriceOye, Telemart, Mega.pk, Surmawala, Ubuy, Shophive, Clicky, Amazon, and eBay. "
        "Built-in request retry loops and header rotation bypass hotlink blocks and CORS restrictions."
    )
    r_g1b.font.size = Pt(9)

    c_g2 = grid2_table.cell(0, 1)
    c_g2.width = Inches(3.6)
    set_cell_background(c_g2, "F8FAFC")
    set_cell_margins(c_g2, top=100, bottom=100, left=120, right=120)
    p_g2 = c_g2.paragraphs[0]
    p_g2.paragraph_format.space_after = Pt(4)
    r_g2 = p_g2.add_run("📈 Price Volatility & Alert Triggers")
    r_g2.font.bold = True
    r_g2.font.size = Pt(10)
    r_g2.font.color.rgb = COLOR_EMERALD

    p_g2b = c_g2.add_paragraph()
    p_g2b.paragraph_format.space_after = Pt(0)
    p_g2b.paragraph_format.line_spacing = 1.15
    r_g2b = p_g2b.add_run(
        "Tracks every product search query in SQLite time-series logs. Interactive Chart.js trend visualizations display 7-day and 30-day price movements, "
        "automatically triggering alert notifications when items reach historical low points."
    )
    r_g2b.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # SECTION 4: MONETIZATION & ADMIN DASHBOARD
    h4_head = doc.add_paragraph()
    h4_head.paragraph_format.space_before = Pt(6)
    h4_head.paragraph_format.space_after = Pt(4)
    hr4 = h4_head.add_run("💼 Affiliate Revenue & Admin Control Portal")
    hr4.font.size = Pt(12)
    hr4.font.bold = True
    hr4.font.color.rgb = COLOR_NAVY

    grid2_table2 = doc.add_table(rows=1, cols=2)
    grid2_table2.alignment = WD_TABLE_ALIGNMENT.CENTER

    c_m1 = grid2_table2.cell(0, 0)
    c_m1.width = Inches(3.6)
    set_cell_background(c_m1, "F8FAFC")
    set_cell_margins(c_m1, top=100, bottom=100, left=120, right=120)
    p_m1 = c_m1.paragraphs[0]
    p_m1.paragraph_format.space_after = Pt(4)
    r_m1 = p_m1.add_run("💰 Affiliate Revenue Tracking")
    r_m1.font.bold = True
    r_m1.font.size = Pt(10)
    r_m1.font.color.rgb = COLOR_EMERALD

    p_m1b = c_m1.add_paragraph()
    p_m1b.paragraph_format.space_after = Pt(0)
    p_m1b.paragraph_format.line_spacing = 1.15
    r_m1b = p_m1b.add_run(
        "Outbound merchant redirect clicks automatically log tracking parameters into the store_clicks database. "
        "The system estimates affiliate commissions (3% standard baseline) to prove commercial viability."
    )
    r_m1b.font.size = Pt(9)

    c_m2 = grid2_table2.cell(0, 1)
    c_m2.width = Inches(3.6)
    set_cell_background(c_m2, "F8FAFC")
    set_cell_margins(c_m2, top=100, bottom=100, left=120, right=120)
    p_m2 = c_m2.paragraphs[0]
    p_m2.paragraph_format.space_after = Pt(4)
    r_m2 = p_m2.add_run("📊 Administrative Management")
    r_m2.font.bold = True
    r_m2.font.size = Pt(10)
    r_m2.font.color.rgb = COLOR_INDIGO

    p_m2b = c_m2.add_paragraph()
    p_m2b.paragraph_format.space_after = Pt(0)
    p_m2b.paragraph_format.line_spacing = 1.15
    r_m2b = p_m2b.add_run(
        "Secured administrative portal (/admin-login) providing live search volume tracking across 7 days, top keyword rankings, "
        "scraper toggle management, contact message inbox, and featured product curation."
    )
    r_m2b.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # IMPACT STATEMENT BOX
    impact_table = doc.add_table(rows=1, cols=1)
    impact_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_imp = impact_table.cell(0, 0)
    cell_imp.width = Inches(7.3)
    set_cell_background(cell_imp, "F0FDF4")
    set_cell_margins(cell_imp, top=120, bottom=120, left=160, right=160)

    pi = cell_imp.paragraphs[0]
    pi.paragraph_format.space_after = Pt(4)
    ri = pi.add_run("🏆 IISAT × InnoVista AI Summit ’26 Innovation & Market Impact")
    ri.font.size = Pt(11)
    ri.font.bold = True
    ri.font.color.rgb = RGBColor(21, 128, 61)

    bullets = [
        ("Democratizing E-Commerce in Emerging Markets: ", "Eliminates price opacity and fragmented product availability across South Asian retail stores."),
        ("Accessibility via Voice AI: ", "Enables voice-assisted search for non-fluent or non-typing users with natural multi-accent phoneme handling."),
        ("AI-Driven Consumer Protection: ", "Protects consumers from deceptive seller reviews and inflated fake discounts through TextBlob NLP Trust Scores and historical validation."),
        ("High Technical Scalability: ", "Lightweight Python micro-architecture deployable on cloud containers (Render/Docker) with sub-second aggregate response times.")
    ]

    for title, desc in bullets:
        p_b = cell_imp.add_paragraph()
        p_b.paragraph_format.space_after = Pt(2)
        p_b.paragraph_format.line_spacing = 1.1
        rb1 = p_b.add_run(f"• {title}")
        rb1.font.bold = True
        rb1.font.size = Pt(8.8)
        rb1.font.color.rgb = RGBColor(22, 101, 52)
        rb2 = p_b.add_run(desc)
        rb2.font.size = Pt(8.8)
        rb2.font.color.rgb = RGBColor(22, 101, 52)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # TEAM & SUBMISSION DETAILS BOX
    team_table = doc.add_table(rows=1, cols=1)
    team_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_t = team_table.cell(0, 0)
    c_t.width = Inches(7.3)
    set_cell_background(c_t, "F8FAFC")
    set_cell_margins(c_t, top=120, bottom=120, left=160, right=160)

    pt = c_t.paragraphs[0]
    pt.paragraph_format.space_after = Pt(4)
    rt = pt.add_run("👥 Team & Submission Information")
    rt.font.size = Pt(10.5)
    rt.font.bold = True
    rt.font.color.rgb = COLOR_NAVY

    p_tinfo = c_t.add_paragraph()
    p_tinfo.paragraph_format.space_after = Pt(0)
    p_tinfo.paragraph_format.line_spacing = 1.2
    r_ti = p_tinfo.add_run(
        "Project Name: Smart Shopping Platform\n"
        "Category: Artificial Intelligence & Full-Stack Web Systems\n"
        "Event: IISAT × InnoVista AI Summit ’26 (Shortlisted Finalist Group)\n"
        "Submitted To: Ms. Malaika Pasha (PMO) — malaika.pasha@iisat.edu.pk"
    )
    r_ti.font.size = Pt(9)
    r_ti.font.color.rgb = COLOR_DARK_TEXT

    # Save to Word Document
    dest_docx_1 = os.path.abspath("IISAT_InnoVista_AI_Summit_26_Smart_Shopping.docx")
    dest_docx_2 = os.path.abspath("../IISAT_InnoVista_AI_Summit_26_Smart_Shopping.docx")

    doc.save(dest_docx_1)
    doc.save(dest_docx_2)

    print(f"SUCCESS: Created docx files at:\n1. {dest_docx_1}\n2. {dest_docx_2}")

if __name__ == '__main__':
    create_docx()
