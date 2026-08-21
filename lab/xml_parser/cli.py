"""Project Mythos — User-friendly CLI for international tax associates.

Usage:
    python -m lab.xml_parser list <file.xml>
    python -m lab.xml_parser parse <file.xml>
    python -m lab.xml_parser compare <prior.xml> <current.xml>
    python -m lab.xml_parser review <prior.xml> <current.xml>

All commands output to terminal AND auto-generate professional reports.
"""

import sys
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.field_maps import get_field_info, format_value, FIELD_MAPS

console = Console()


@click.group()
@click.version_option(package_name="mythos", prog_name="mythos")
def cli():
    """Project Mythos — Parse and compare IRS e-file XMLs."""
    pass


@cli.command()
@click.argument("xml_file", type=click.Path(exists=True))
def list(xml_file):
    """Quick summary of all entities in the XML."""
    console.print(Panel.fit("[bold]Project Mythos[/bold] — Entity List", style="orange1"))

    parser = EFileParser(xml_file)
    header = parser._parse_header()
    entities = parser.list_subsidiaries()

    console.print(f"\n[bold]Client:[/bold] {header.filer_name}")
    console.print(f"[bold]Tax Year:[/bold] {header.tax_year}")
    console.print(f"[bold]Return Type:[/bold] {header.return_type}")
    console.print(f"[bold]Entities:[/bold] {len(entities)}\n")

    table = Table(title=f"Subsidiary Entities ({len(entities)})")
    table.add_column("#", style="dim", width=4)
    table.add_column("Entity Name", style="bold", min_width=35)
    table.add_column("Ref ID", width=8)
    table.add_column("Country", width=8)
    table.add_column("Currency", width=8)
    table.add_column("Dormant", width=8)

    for i, e in enumerate(entities, 1):
        dormant_str = "[red]Yes[/red]" if e["dormant"] else ""
        table.add_row(
            str(i), e["name"], e["reference_id"],
            e["country_code"], e["functional_currency"], dormant_str
        )

    console.print(table)


@cli.command()
@click.argument("xml_file", type=click.Path(exists=True))
@click.option("--form", "-f", multiple=True, help="Forms to extract (e.g., IRS5471ScheduleH)")
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
@click.option("--entity", "-e", help="Filter to specific entity (by name or ref ID)")
def parse(xml_file, form, output, entity):
    """Parse an XML file and display/export form data."""
    console.print(Panel.fit("[bold]Project Mythos[/bold] — Parse Mode", style="orange1"))

    parser = EFileParser(xml_file)
    header = parser._parse_header()

    console.print(f"\n[bold]Client:[/bold] {header.filer_name}")
    console.print(f"[bold]Tax Year:[/bold] {header.tax_year}")
    console.print(f"[bold]File:[/bold] {Path(xml_file).name}\n")

    forms_to_parse = list(form) if form else [
        "IRS5471", "IRS5471ScheduleH", "IRS5471ScheduleI1",
        "IRS5471ScheduleE", "IRS5471ScheduleJ", "IRS5471ScheduleQ"
    ]

    # Generate output path if not specified
    if not output:
        stem = Path(xml_file).stem
        output = str(Path(xml_file).parent / f"{stem}_parsed.xlsx")

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for form_name in forms_to_parse:
            df = parser.extract_form(form_name)
            if df.empty:
                console.print(f"  [dim]{form_name}: no data[/dim]")
                continue

            if entity:
                mask = df["_entity_name"].str.contains(entity, case=False, na=False) | \
                       df["_reference_id"].str.contains(entity, case=False, na=False)
                df = df[mask]

            # Clean column names for Excel tab
            short_name = form_name.replace("IRS5471", "5471").replace("Schedule", "Sch")
            df.to_excel(writer, sheet_name=short_name[:31], index=False)

            # Terminal display
            console.print(f"  [green]✓[/green] {form_name}: {len(df)} entities × {len(df.columns)} fields")

            # Show summary for Schedule H (most common review)
            if "ScheduleH" in form_name and not df.empty:
                _display_schedule_h_summary(df)

    console.print(f"\n[bold green]Output saved:[/bold green] {output}")


@cli.command(deprecated=True)
@click.argument("prior_xml", type=click.Path(exists=True))
@click.argument("current_xml", type=click.Path(exists=True))
@click.option("--form", "-f", multiple=True, help="Forms to compare")
@click.option("--threshold", "-t", default=1000, help="Material change threshold ($)")
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
def compare(prior_xml, current_xml, form, threshold, output):
    """[Deprecated] Use 'review' command instead — it includes full comparison + 71 checks."""
    console.print("[bold yellow]⚠ The 'compare' command is deprecated.[/bold yellow]")
    console.print("Use [bold]mythos review[/bold] instead — it includes rollover comparison with 71 automated checks.")
    raise SystemExit(1)


def _display_schedule_h_summary(df):
    """Display a quick Schedule H summary in the terminal."""
    table = Table(title="Schedule H — E&P Summary (Top entities)", show_lines=False)
    table.add_column("Entity", style="bold", min_width=30)
    table.add_column("Ref ID", width=7)
    table.add_column("Current E&P (USD)", justify="right", width=18)
    table.add_column("Net Income", justify="right", width=15)

    ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
    inc_col = "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt"

    if ep_col not in df.columns:
        return

    df_sorted = df.copy()
    df_sorted[ep_col] = pd.to_numeric(df_sorted[ep_col], errors="coerce")
    df_sorted = df_sorted.sort_values(ep_col, key=abs, ascending=False).head(10)

    for _, row in df_sorted.iterrows():
        ep = row.get(ep_col, 0)
        inc = row.get(inc_col, 0)
        try:
            ep_val = -float(ep) if ep and str(ep) != "nan" else 0
            inc_val = -float(inc) if inc and str(inc) != "nan" else 0
            ep_str = f"${ep_val/1e6:,.2f}M" if abs(ep_val) >= 1e6 else f"${ep_val/1e3:,.1f}K"
            inc_str = f"${inc_val/1e6:,.2f}M" if abs(inc_val) >= 1e6 else f"${inc_val/1e3:,.1f}K"
        except (ValueError, TypeError):
            ep_str = "—"
            inc_str = "—"

        table.add_row(
            str(row.get("_entity_name", ""))[:30],
            str(row.get("_reference_id", "")),
            ep_str, inc_str
        )

    console.print(table)


@cli.command()
@click.argument("prior_xml", type=click.Path(exists=True))
@click.argument("current_xml", type=click.Path(exists=True))
@click.option("--client", "-c", default="", help="Client name for report header")
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
@click.option("--format", "-fmt", "output_format", type=click.Choice(["excel", "html", "pdf", "all"]), default="excel", help="Output format")
@click.option("--html-dir", type=click.Path(), help="Directory for HTML output (default: next to XML)")
@click.option("--form", "form_type", type=click.Choice(["auto", "5471", "8858"]), default="auto", help="Form type (default: auto-detect)")
@click.option("--entity", "-e", multiple=True, help="Filter to specific entities (code or name, repeatable)")
@click.option("--check", multiple=True, help="Filter to specific checks (FLO-003) or report types (sch_f)")
@click.option("--category", multiple=True, help="Filter to category (flow, completeness, reasonableness, rollover)")
def review(prior_xml, current_xml, client, output, output_format, html_dir, form_type, entity, check, category):
    """Full rollover review — auto-detects forms and runs all applicable checks."""
    from lab.xml_parser.reports import run_all_reports, run_all_reports_8858, run_all_reports_unified
    from lab.xml_parser.review_engine import ReviewEngine
    from lab.xml_parser.export import export_html, export_pdf, export_excel
    from lab.xml_parser.core.filters import build_filter_spec, filter_review_report, filter_rollover_reports
    from lab.xml_parser.parser import EFileParser

    console.print(Panel.fit("[bold]Project Mythos[/bold] — Full Rollover Review", style="orange1"))

    base_dir = Path(current_xml).parent

    # Detect or use explicit form type
    if form_type == "auto":
        parser = EFileParser(current_xml)
        forms = parser.detect_forms()
        console.print(f"  [dim]Auto-detected forms: {', '.join(sorted(forms)) or 'none'}[/dim]")
    else:
        forms = {form_type}

    # Run reports
    with console.status("Generating reports..."):
        if form_type == "auto":
            rollover_reports = run_all_reports_unified(prior_xml, current_xml)
        elif form_type == "8858":
            rollover_reports = run_all_reports_8858(prior_xml, current_xml)
        else:
            rollover_reports = run_all_reports(prior_xml, current_xml)

    # Run checks
    with console.status("Running automated checks..."):
        engine = ReviewEngine()
        if form_type == "auto":
            review_report = engine.review_all(current_xml, prior_xml)
        else:
            review_report = engine.review(current_xml, prior_xml, form_type=form_type)

    tax_year = review_report.tax_year

    # Apply filters if any
    spec = build_filter_spec(
        entities=list(entity) if entity else None,
        checks=list(check) if check else None,
        categories=list(category) if category else None,
    )
    if not spec.is_empty:
        console.print(f"\n[dim]Filters: {_describe_filter(spec)}[/dim]")
        rollover_reports = filter_rollover_reports(rollover_reports, spec)
        if review_report:
            review_report = filter_review_report(review_report, spec)

    # Terminal summary
    console.print(f"\n[bold]Client:[/bold] {review_report.client_name}")
    console.print(f"[bold]Tax Year:[/bold] {tax_year}")
    console.print(f"[bold]Entities:[/bold] {review_report.entity_count}")
    console.print(f"[bold]Forms:[/bold] {', '.join(sorted(forms))}")

    summary_table = Table(title="Report Summary", show_lines=True)
    summary_table.add_column("Report", style="bold", width=25)
    summary_table.add_column("Checks", justify="center", width=8)
    summary_table.add_column("Pass", justify="center", width=8, style="green")
    summary_table.add_column("Fail", justify="center", width=8, style="red")

    for name, report in rollover_reports.items():
        summary_table.add_row(name, str(report.total_checks), str(report.passed), str(report.failed))
    console.print(summary_table)

    if review_report.findings:
        high = review_report.high_severity()
        console.print(f"\n[bold orange1]Automated Checks:[/bold orange1] {len(review_report.findings)} findings "
                     f"({len(high)} HIGH)")
        for f in high[:10]:
            console.print(f"  [red]HIGH[/red]  {f.check_id}  {f.entity_code:<8}  {f.description[:60]}")

    # Excel export (default)
    if output_format in ("excel", "all"):
        excel_path = Path(output) if output else base_dir / f"Review_{Path(current_xml).stem}.xlsx"
        export_excel(
            excel_path,
            review_report=review_report,
            rollover_reports=rollover_reports,
            client_name=client or review_report.client_name,
        )
        console.print(f"\n[bold green]Excel saved:[/bold green] {excel_path}")

    if output_format in ("html", "all"):
        html_output = Path(html_dir) if html_dir else base_dir / f"review_html_{Path(current_xml).stem}"
        files = export_html(rollover_reports, html_output, client_name=client, tax_year=tax_year)
        console.print(f"\n[bold green]HTML saved:[/bold green] {html_output}/")
        for f in files:
            console.print(f"  {f.name}")

    if output_format in ("pdf", "all"):
        pdf_path = base_dir / f"Review_{Path(current_xml).stem}.pdf"
        export_pdf(
            pdf_path,
            review_report=review_report,
            rollover_reports=rollover_reports,
            client_name=client,
            tax_year=tax_year,
        )
        console.print(f"\n[bold green]PDF saved:[/bold green] {pdf_path}")


def _describe_filter(spec) -> str:
    parts = []
    if spec.entity_codes:
        parts.append(f"entities={','.join(sorted(spec.entity_codes))}")
    if spec.entity_names:
        parts.append(f"names={','.join(sorted(spec.entity_names))}")
    if spec.check_ids:
        parts.append(f"checks={','.join(sorted(spec.check_ids))}")
    if spec.check_categories:
        parts.append(f"categories={','.join(sorted(spec.check_categories))}")
    if spec.report_keys:
        parts.append(f"reports={','.join(sorted(spec.report_keys))}")
    return " | ".join(parts) if parts else "none"


@cli.command()
@click.argument("xml_file", type=click.Path(exists=True))
@click.argument("workbook", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
@click.option("--tolerance", "-t", default=1.0, help="Numeric tolerance for matching (default: $1)")
@click.option("--schedule", "-s", multiple=True, help="Specific schedules to reconcile (default: all)")
def reconcile(xml_file, workbook, output, tolerance, schedule):
    """Reconcile workbook data against XML — field-by-field comparison."""
    from lab.xml_parser.workbook_reader import WorkbookReader
    from lab.xml_parser.reconciler import Reconciler

    console.print(Panel.fit("[bold]Project Mythos[/bold] — Workbook vs XML Reconciliation", style="orange1"))

    # Parse both sources
    with console.status("Parsing XML..."):
        parser = EFileParser(xml_file)
        parser.parse()

    with console.status("Parsing workbook..."):
        with WorkbookReader(workbook) as reader:
            wb_data = reader.parse()

    console.print(f"  XML: {Path(xml_file).name} ({len(parser.list_subsidiaries())} entities)")
    console.print(f"  Workbook: {Path(workbook).name} ({wb_data.entity_count} entities, {len(wb_data.schedules)} schedules)")

    # Run reconciliation
    schedules_list = list(schedule) if schedule else None
    rec = Reconciler(tolerance=tolerance)
    report = rec.reconcile(wb_data, parser, schedules=schedules_list)

    # Display summary
    s = report.summary
    console.print(f"\n[bold]Results:[/bold] {s['total']} comparisons")
    console.print(f"  [green]PASS:[/green] {s['pass_count']}  "
                  f"[red]FAIL:[/red] {s['fail_count']}  "
                  f"[yellow]DORMANT_OK:[/yellow] {s['dormant_ok']}  "
                  f"[dim]XML_MISSING:[/dim] {s['xml_missing']}")
    console.print(f"  Pass rate: [bold]{s['pass_rate']:.1%}[/bold]")

    # By schedule
    table = Table(title="By Schedule", show_lines=False)
    table.add_column("Schedule", style="bold")
    table.add_column("Pass", justify="right", style="green")
    table.add_column("Fail", justify="right", style="red")
    table.add_column("Dormant", justify="right", style="yellow")
    table.add_column("Rate", justify="right")

    for sched, stats in s.get("by_schedule", {}).items():
        comparable = stats["total"] - stats.get("xml_missing", 0)
        rate = (stats["pass"] + stats["dormant_ok"]) / comparable if comparable > 0 else 0
        table.add_row(sched, str(stats["pass"]), str(stats["fail"]),
                     str(stats["dormant_ok"]), f"{rate:.0%}")
    console.print(table)

    # Top failures
    fails = report.failures_only()
    if not fails.empty:
        console.print(f"\n[bold red]Top Failures ({len(fails)} total):[/bold red]")
        fail_table = Table(show_lines=False)
        fail_table.add_column("Entity", width=7)
        fail_table.add_column("Schedule", width=10)
        fail_table.add_column("Field", width=30)
        fail_table.add_column("WB", justify="right", width=15)
        fail_table.add_column("XML", justify="right", width=15)
        fail_table.add_column("Delta", justify="right", width=12)

        for _, row in fails.head(15).iterrows():
            wb_str = f"{row['wb_value']:,.0f}" if isinstance(row['wb_value'], (int, float)) else str(row['wb_value'])
            xml_str = f"{row['xml_value']:,.0f}" if isinstance(row['xml_value'], (int, float)) else str(row['xml_value'])
            d = row['delta']
            delta_str = f"{d:,.0f}" if d and d > 0 else ""
            fail_table.add_row(row['entity_code'], row['schedule'], row['field_name'],
                             wb_str, xml_str, delta_str)
        console.print(fail_table)

    # Export
    if not output:
        output = str(Path(workbook).parent / f"reconciliation_{Path(workbook).stem}.xlsx")
    report.to_excel(output)
    console.print(f"\n[bold green]Excel saved:[/bold green] {output}")


@cli.command("check")
@click.argument("current_xml", type=click.Path(exists=True))
@click.option("--prior", "-p", type=click.Path(exists=True), help="Prior year XML for rollover checks")
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
def check(current_xml, prior, output):
    """Run automated review checks on XML return (no workbook needed)."""
    from lab.xml_parser.review_engine import ReviewEngine

    console.print(Panel.fit("[bold]Project Mythos[/bold] — Automated Review Engine", style="orange1"))

    with console.status("Running review checks..."):
        engine = ReviewEngine()
        report = engine.review(current_xml, prior)

    # Summary
    s = report.summary
    console.print(f"\n  Client: [bold]{report.client_name}[/bold]")
    console.print(f"  Tax Year: {report.tax_year}")
    console.print(f"  Entities: {report.entity_count}")
    console.print(f"  Rollover: {'enabled' if prior else 'disabled'}")
    console.print()

    # Severity counts
    high = s["by_severity"]["HIGH"]
    med = s["by_severity"]["MEDIUM"]
    low = s["by_severity"]["LOW"]
    console.print(f"  [bold]Findings:[/bold] {s['total_findings']} total")
    console.print(f"    [red]HIGH:[/red] {high}  [yellow]MEDIUM:[/yellow] {med}  [dim]LOW:[/dim] {low}")
    console.print(f"    Clean entities: {s['clean_entities']}/{report.entity_count}")

    # Findings table
    if report.findings:
        table = Table(title="Review Findings", show_lines=False)
        table.add_column("Sev", width=6)
        table.add_column("Check", width=8)
        table.add_column("Category", width=12)
        table.add_column("Entity", width=12)
        table.add_column("Description", min_width=40)

        for f in report.findings[:30]:
            sev_style = "red bold" if f.severity == "HIGH" else "yellow" if f.severity == "MEDIUM" else "dim"
            table.add_row(
                Text(f.severity, style=sev_style),
                f.check_id,
                f.category,
                f.entity_code,
                f.description[:80],
            )
        console.print(table)

        if len(report.findings) > 30:
            console.print(f"  ... and {len(report.findings) - 30} more findings")

    # Export
    if not output:
        output = str(Path(current_xml).parent / f"review_{Path(current_xml).stem}.xlsx")
    df = report.to_dataframe()
    if not df.empty:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            df[df["severity"] == "HIGH"].to_excel(writer, sheet_name="High Severity", index=False)
        console.print(f"\n[bold green]Excel saved:[/bold green] {output}")


@cli.command("tag")
@click.argument("xml_file", type=click.Path(exists=True))
@click.option("--entity", "-e", help="Filter to specific entity (code or name)")
@click.option("--detail", is_flag=True, help="Show full entity profiles with schedule presence")
def tag(xml_file, entity, detail):
    """Classify entities by fiscal behavior (GILTI, SubF, dormant, etc.)."""
    from lab.xml_parser.api.service import MythosService

    console.print(Panel.fit("[bold]Project Mythos[/bold] — Entity Classifier", style="orange1"))

    svc = MythosService()
    result = svc.classify_entities(xml_file)

    if not result.success:
        console.print(f"[red]Error:[/red] {result.message}")
        raise SystemExit(1)

    summary = result.summary
    console.print(f"\n  Entities: [bold]{summary.total_entities}[/bold]")
    console.print(f"  Contradictions: [bold]{len(summary.contradictions)}[/bold]")
    console.print(f"  Duration: {result.duration_ms:.0f}ms\n")

    if detail:
        # Full entity profile cards
        for e in result.entities:
            if entity:
                if entity.lower() not in e.entity_name.lower() and entity != e.reference_id:
                    continue

            tag_strs = []
            for t in sorted(e.tags):
                if t in ("tested_loss", "negative_ep"):
                    tag_strs.append(f"[red]{t}[/red]")
                elif t in ("dormant", "dre"):
                    tag_strs.append(f"[dim]{t}[/dim]")
                elif t in ("subpart_f", "us_property", "income_blocked"):
                    tag_strs.append(f"[yellow]{t}[/yellow]")
                elif t in ("tested_income", "has_qbai", "full_inclusion"):
                    tag_strs.append(f"[green]{t}[/green]")
                else:
                    tag_strs.append(t)

            sch_flags = ""
            sch_flags += "C" if e.has_sch_c else "."
            sch_flags += "E" if e.has_sch_e else "."
            sch_flags += "H" if e.has_sch_h else "."
            sch_flags += "I" if e.has_sch_i else "."
            sch_flags += "1" if e.has_sch_i1 else "."
            sch_flags += "J" if e.has_sch_j else "."
            sch_flags += "P" if e.has_sch_p else "."

            location = ", ".join(filter(None, [e.city, e.province, e.country_code]))
            warn_str = " [red]CONTRADICTIONS[/red]" if e.contradictions else ""

            console.print(f"\n  [bold]{e.entity_name}[/bold] ({e.reference_id}){warn_str}")
            console.print(f"    Form: {e.form_type}  |  EIN: {e.ein or '—'}  |  FC: {e.functional_currency}  |  Country: {e.country_code}")
            console.print(f"    Address: {e.address_line1 or '—'}, {location}  {e.postal_code}")
            if e.incorporation_date:
                console.print(f"    Incorporated: {e.incorporation_date}")
            if e.principal_place_of_business and e.principal_place_of_business != e.country_code:
                console.print(f"    Principal Place of Business: {e.principal_place_of_business}")
            if e.voting_stock_pct is not None:
                console.print(f"    Voting Stock: {e.voting_stock_pct:.0%}")
            if e.category_filers:
                console.print(f"    Category Filers: {', '.join(e.category_filers)}")
            if e.tax_owner_name:
                console.print(f"    Tax Owner: {e.tax_owner_name} ({e.tax_owner_ref_id})")
            console.print(f"    Schedules: [dim]{sch_flags}[/dim]  |  Tags: {', '.join(tag_strs) or '[dim]none[/dim]'}")

    else:
        # Compact table view
        table = Table(title=f"Entity Classification ({summary.total_entities} entities)", show_lines=False)
        table.add_column("Ref", width=7)
        table.add_column("Entity Name", style="bold", min_width=25)
        table.add_column("CC", width=4)
        table.add_column("FC", width=5)
        table.add_column("Tags", min_width=45)
        table.add_column("!", width=3, justify="center")

        for e in result.entities:
            if entity:
                if entity.lower() not in e.entity_name.lower() and entity != e.reference_id:
                    continue

            tag_strs = []
            for t in sorted(e.tags):
                if t in ("tested_loss", "negative_ep"):
                    tag_strs.append(f"[red]{t}[/red]")
                elif t in ("dormant", "dre"):
                    tag_strs.append(f"[dim]{t}[/dim]")
                elif t in ("subpart_f", "us_property", "income_blocked"):
                    tag_strs.append(f"[yellow]{t}[/yellow]")
                elif t in ("tested_income", "has_qbai", "full_inclusion"):
                    tag_strs.append(f"[green]{t}[/green]")
                else:
                    tag_strs.append(t)

            warn = "[red]![/red]" if e.contradictions else ""
            table.add_row(e.reference_id, e.entity_name[:30], e.country_code, e.functional_currency, ", ".join(tag_strs), warn)

        console.print(table)

    # Summary
    if summary.by_tag:
        console.print("\n[bold]Tag Distribution:[/bold]")
        for tag_name, count in summary.by_tag.items():
            bar = "#" * min(count, 30)
            console.print(f"  {tag_name:<22} {count:>3}  [dim]{bar}[/dim]")

    # Type breakdown
    if summary.by_type:
        console.print("\n[bold]Entity Types:[/bold]")
        for t, count in sorted(summary.by_type.items(), key=lambda x: -x[1]):
            console.print(f"  {t:<12} {count}")

    # Contradictions detail
    if summary.contradictions:
        console.print(f"\n[bold red]Contradictions ({len(summary.contradictions)}):[/bold red]")
        for ref, tag_a, tag_b, reason in summary.contradictions:
            console.print(f"  [red]![/red] {ref}: {tag_a} + {tag_b} -- {reason}")


@cli.command("dashboard")
@click.option("--port", default=8080, help="Port for the dashboard server")
@click.option("--web", is_flag=True, help="Open in browser instead of native window")
def dashboard(port, web):
    """Launch the Mythos dashboard (native desktop app or web)."""
    console.print(Panel.fit("[bold]Project Mythos[/bold] — Dashboard", style="orange1"))

    from nicegui import ui
    import lab.xml_parser.dashboard  # noqa: registers pages

    if web:
        console.print(f"  Starting web mode on http://localhost:{port}")
        ui.run(title="Mythos", port=port, reload=False)
    else:
        console.print("  Launching native window...")
        ui.run(title="Mythos", native=True, window_size=(1400, 900), reload=False)


if __name__ == "__main__":
    cli()
