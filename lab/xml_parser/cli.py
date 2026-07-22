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
from lab.xml_parser.comparator import XMLComparator
from lab.xml_parser.field_maps import get_field_info, format_value, FIELD_MAPS

console = Console()


@click.group()
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


@cli.command()
@click.argument("prior_xml", type=click.Path(exists=True))
@click.argument("current_xml", type=click.Path(exists=True))
@click.option("--form", "-f", multiple=True, help="Forms to compare")
@click.option("--threshold", "-t", default=1000, help="Material change threshold ($)")
@click.option("--output", "-o", type=click.Path(), help="Output Excel path")
def compare(prior_xml, current_xml, form, threshold, output):
    """Compare two XMLs (e.g., PY vs CY) and flag rollover differences."""
    console.print(Panel.fit("[bold]Project Mythos[/bold] — Compare Mode (Rollover Review)", style="orange1"))

    p1 = EFileParser(prior_xml)
    p2 = EFileParser(current_xml)
    h1 = p1._parse_header()
    h2 = p2._parse_header()

    console.print(f"\n[bold]Prior Year:[/bold] {Path(prior_xml).name} (TY{h1.tax_year})")
    console.print(f"[bold]Current Year:[/bold] {Path(current_xml).name} (TY{h2.tax_year})")
    console.print(f"[bold]Threshold:[/bold] ${threshold:,}\n")

    forms_to_compare = list(form) if form else [
        "IRS5471ScheduleH", "IRS5471ScheduleI1", "IRS5471ScheduleE"
    ]

    comp = XMLComparator(threshold=threshold)
    report = comp.compare(prior_xml, current_xml, forms=forms_to_compare)

    # Summary panel
    summary_text = Text()
    summary_text.append(f"Entities added: ", style="dim")
    summary_text.append(f"{len(report.entities_added)}\n", style="green" if report.entities_added else "dim")
    summary_text.append(f"Entities removed: ", style="dim")
    summary_text.append(f"{len(report.entities_removed)}\n", style="red" if report.entities_removed else "dim")
    summary_text.append(f"Entities modified: ", style="dim")
    summary_text.append(f"{len(report.entities_modified)}\n", style="yellow")
    summary_text.append(f"Total field changes: ", style="dim")
    summary_text.append(f"{report.total_field_changes}\n")
    summary_text.append(f"Material changes (>${threshold:,}): ", style="dim")
    summary_text.append(f"{report.material_changes}", style="bold red" if report.material_changes else "green")

    console.print(Panel(summary_text, title="Comparison Summary"))

    # Material changes table
    if report.material_changes > 0:
        table = Table(title=f"Material Changes (>${threshold:,})")
        table.add_column("Entity", style="bold", min_width=25)
        table.add_column("Line", width=8)
        table.add_column("Description", min_width=30)
        table.add_column("Prior Year", justify="right", width=15)
        table.add_column("Current Year", justify="right", width=15)
        table.add_column("Change", justify="right", width=14, style="bold")

        shown = 0
        for ec in report.entities_modified:
            for fc in ec.field_changes:
                if not fc.material or shown >= 50:
                    continue
                # Determine form name from field prefix
                form_prefix = fc.field.split("_")[0] if "_" in fc.field else ""
                full_form = f"IRS5471{form_prefix}" if form_prefix.startswith("Schedule") else "IRS5471ScheduleH"
                info = get_field_info(full_form, fc.field)

                old_fmt = format_value(fc.old_value, info)
                new_fmt = format_value(fc.new_value, info)

                if fc.numeric_diff:
                    sign_adj = -fc.numeric_diff if info.get("sign") == "negative_is_income" else fc.numeric_diff
                    if abs(sign_adj) >= 1e6:
                        diff_str = f"[{'green' if sign_adj > 0 else 'red'}]{sign_adj/1e6:+,.2f}M[/]"
                    else:
                        diff_str = f"[{'green' if sign_adj > 0 else 'red'}]{sign_adj/1e3:+,.1f}K[/]"
                else:
                    diff_str = "—"

                table.add_row(
                    ec.entity_name[:25], info["line"], info["description"][:30],
                    old_fmt, new_fmt, diff_str
                )
                shown += 1

        console.print(table)

    # Added/Removed entities
    if report.entities_added:
        console.print(f"\n[green]Added entities:[/green] {', '.join(report.entities_added[:10])}")
    if report.entities_removed:
        console.print(f"\n[red]Removed entities:[/red] {', '.join(report.entities_removed[:10])}")
        if len(report.entities_removed) > 10:
            console.print(f"  ... and {len(report.entities_removed)-10} more")

    # Export to Excel
    if not output:
        stem1 = Path(prior_xml).stem
        stem2 = Path(current_xml).stem
        output = str(Path(current_xml).parent / f"compare_{stem1}_vs_{stem2}.xlsx")

    df_report = comp.to_dataframe(report)
    df_report.to_excel(output, index=False, sheet_name="Comparison")
    console.print(f"\n[bold green]Excel saved:[/bold green] {output}")


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
def review(prior_xml, current_xml, client, output, output_format, html_dir):
    """Full rollover review — run all 7 automated checks and generate reports."""
    from lab.xml_parser.reports import ReportEngine
    from lab.xml_parser.output import export_excel, export_pdf_branded
    from lab.xml_parser.gt_output import gt_full_review

    console.print(Panel.fit("[bold]Project Mythos[/bold] — Full Rollover Review", style="orange1"))

    engine = ReportEngine(prior_xml, current_xml)

    # Run all reports (this also prints the terminal summary)
    reports = engine.full_review(output_path=output)

    # Additional formats
    tax_year = engine._cy.header.tax_year
    base_dir = Path(current_xml).parent

    if output_format in ("html", "all"):
        html_output = Path(html_dir) if html_dir else base_dir / f"review_html_{Path(current_xml).stem}"
        files = gt_full_review(reports, html_output, client_name=client, tax_year=tax_year)
        console.print(f"\n[bold green]HTML saved:[/bold green] {html_output}/")
        for f in files:
            console.print(f"  {f.name}")

    if output_format in ("pdf", "all"):
        pdf_path = base_dir / f"Review_{Path(current_xml).stem}.pdf"
        export_pdf_branded(reports, pdf_path, client_name=client, tax_year=tax_year)
        console.print(f"\n[bold green]PDF saved:[/bold green] {pdf_path}")


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
