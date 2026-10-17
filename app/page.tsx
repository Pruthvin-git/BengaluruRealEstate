"use client";

import dynamic from "next/dynamic";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DetailDrawer, type OrderRow } from "../components/DetailDrawer";
import type { MapPin } from "../components/ProjectMap";

const ProjectMap = dynamic(() => import("../components/ProjectMap").then(mod => mod.ProjectMap), {
  ssr: false,
  loading: () => <section className="map-card"><p className="loading">Loading the Bengaluru map…</p></section>,
});
import { parseCsv } from "../lib/csv";
import { indexByName, lookupName, type NameIndex } from "../lib/names";
import {
  bookingForPeriod,
  inventoryShares,
  inventoryStats,
  latestBooking,
  numeric,
  projectCountForPeriod,
  quarterlyInventoryStats,
  reportingPeriods,
  totalUnits,
  value,
  type Project,
} from "../lib/project-metrics";
import { extractSurveys } from "../lib/survey";

type Sort = { key: string; direction: "asc" | "desc" };
type Column = readonly [string, string];

const columns: Column[] = [
  ["Project Name", "Project Name"],
  ["Approved On", "Approved On"],
  ["Proposed Completion Date", "Proposed Completion Date"],
  ["Total Units", "Total Units"],
  ["Units Booked (Q2_FY26-27)", "Booked · Sep 2026"],
  ["Units Available (Q2_FY26-27)", "Unsold · Sep 2026"],
  ["bookedPercent", "Booked %"],
  ["complaints", "Complaints"],
  ["promoterComplaints", "Promoter complaints"],
  ["surveys", "Survey nos"],
  ["Builder", "Builder"],
  ["Promoter Name", "Promoter Name"],
  ["District", "District"],
  ["Taluka", "Taluka"],
  ["Project Type", "Project Type"],
  ["Proposed Completion Date At Registration", "Proposed Completion Date At Registration"],
  ["Project Address", "Project Address"],
  ["Has Quarterly Update", "Has Quarterly Update"],
  ["Units Booked (Q3_FY25-26)", "Booked · Dec 2025"],
  ["Units Available (Q3_FY25-26)", "Unsold · Dec 2025"],
  ["Units Booked (Q4_FY25-26)", "Booked · Mar 2026"],
  ["Units Available (Q4_FY25-26)", "Unsold · Mar 2026"],
  ["Registration Number", "RERA ID"],
];

const PAGE_SIZE = 80;
const MIN_COLUMN_WIDTH = 100;
const MAX_COLUMN_WIDTH = 800;
const columnSearchFields: Record<string, string> = {
  "Project Name": "Search projects",
  Builder: "Search developers",
  "Promoter Name": "Search promoters",
  "Registration Number": "Search RERA IDs",
};

function defaultColumnWidth(key: string) {
  if (["Project Name", "Builder", "Promoter Name", "Project Address"].includes(key)) return 250;
  if (key === "Registration Number" || key === "Proposed Completion Date At Registration") return 280;
  if (key === "complaints" || key === "surveys" || key === "promoterComplaints") return 130;
  return 160;
}

function dateInRange(value: string, start: string, end: string) {
  return (!start || value >= start) && (!end || value <= end);
}

const MultiSelect = memo(function MultiSelect({
  label,
  options,
  selected,
  setSelected,
}: {
  label: string;
  options: string[];
  selected: string[];
  setSelected: (value: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const shown = useMemo(
    () => options.filter(option => option.toLowerCase().includes(query.toLowerCase())).slice(0, 80),
    [options, query],
  );
  const toggle = (value: string) =>
    setSelected(selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value]);
  return (
    <fieldset className="filter">
      <legend>
        {label} <span>{selected.length ? selected.length : "All"}</span>
      </legend>
      <input value={query} onChange={event => setQuery(event.target.value)} placeholder={`Search ${label.toLowerCase()}`} />
      <div className="choices">
        {shown.map(option => (
          <label key={option}>
            <input type="checkbox" checked={selected.includes(option)} onChange={() => toggle(option)} />
            <span>{option}</span>
          </label>
        ))}
        {!shown.length && <p className="no-options">No matches</p>}
      </div>
    </fieldset>
  );
});

function Metric({
  label,
  value: amount,
  history,
  description,
  percentage,
  status,
}: {
  label: string;
  value: string;
  history?: { label: string; value: string; percentage?: number | null }[];
  description?: string;
  percentage?: number | null;
  status?: "unknown" | "booked" | "unsold";
}) {
  return (
    <article className={status ? `metric metric--${status}` : "metric"}>
      <span>{label}</span>
      <em className="metric-period">Sep 2026*</em>
      <strong>
        {amount}
        {percentage !== undefined && (
          <small className="metric-percentage">({percentage === null ? "—" : `${percentage.toFixed(1)}%`})</small>
        )}
      </strong>
      <p className="metric-description">{description || "\u00a0"}</p>
      <dl className="metric-history">
        {history?.map(row => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>
              {row.value}
              {row.percentage !== undefined && row.percentage !== null && <small> ({row.percentage.toFixed(1)}%)</small>}
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function extraValue(
  project: Project,
  key: string,
  projectComplaints: NameIndex,
  promoterComplaints: NameIndex,
): number | string | null {
  if (key === "complaints") return lookupName(projectComplaints, project["Project Name"])?.count ?? 0;
  if (key === "promoterComplaints") return lookupName(promoterComplaints, project["Promoter Name"])?.count ?? 0;
  if (key === "surveys") return extractSurveys(project["Project Address"]).length;
  return value(project, key);
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const emptyIndex: NameIndex = { exact: new Map(), byToken: new Map() };
  const [projectComplaints, setProjectComplaints] = useState<NameIndex>(emptyIndex);
  const [promoterComplaints, setPromoterComplaints] = useState<NameIndex>(emptyIndex);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [columnOrder, setColumnOrder] = useState<Column[]>(() => [...columns]);
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [page, setPage] = useState(0);
  const [columnSearch, setColumnSearch] = useState<Record<string, string>>({});
  const [projectNames, setProjectNames] = useState<string[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [builders, setBuilders] = useState<string[]>([]);
  const [promoters, setPromoters] = useState<string[]>([]);
  const [talukas, setTalukas] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [completionStart, setCompletionStart] = useState("");
  const [completionEnd, setCompletionEnd] = useState("");
  const [approvalStart, setApprovalStart] = useState("");
  const [approvalEnd, setApprovalEnd] = useState("");
  const [minimumUnits, setMinimumUnits] = useState("");
  const [maximumUnits, setMaximumUnits] = useState("");
  const [hasUpdate, setHasUpdate] = useState(false);
  const [hasComplaints, setHasComplaints] = useState(false);
  const [sort, setSort] = useState<Sort>({ key: "Total Units", direction: "desc" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [complaintFocus, setComplaintFocus] = useState<"project" | "promoter" | null>(null);
  const dragOrigin = useRef<{ key: string; x: number; width: number } | null>(null);

  useEffect(() => {
    fetch("/projects.csv").then(response => response.text()).then(text => setProjects(parseCsv(text)));
    fetch("/data/project-complaints.json").then(response => response.json()).then(body => setProjectComplaints(indexByName(body.items ?? []))).catch(() => undefined);
    fetch("/data/promoter-complaints.json").then(response => response.json()).then(body => setPromoterComplaints(indexByName(body.items ?? []))).catch(() => undefined);
    fetch("/data/orders.json").then(response => response.json()).then(body => setOrders(body.items ?? [])).catch(() => undefined);
  }, []);

  const filterOptions = useMemo(() => {
    const keys = ["Project Name", "District", "Taluka", "Builder", "Promoter Name", "Project Type"] as const;
    return Object.fromEntries(
      keys.map(key => [
        key,
        [...new Set(projects.map(project => project[key]).filter(item => item && item !== "NA"))].sort((a, b) => a.localeCompare(b)),
      ]),
    ) as Record<(typeof keys)[number], string[]>;
  }, [projects]);

  const unitsBounds = useMemo(() => {
    const units = projects.map(project => totalUnits(project)).filter((item): item is number => item !== null);
    return units.length ? ([Math.min(...units), Math.max(...units)] as const) : null;
  }, [projects]);

  const filtered = useMemo(() => {
    const rows = projects.filter(project => {
      const units = totalUnits(project);
      const complaintCount = lookupName(projectComplaints, project["Project Name"])?.count ?? 0;
      const promoterCount = lookupName(promoterComplaints, project["Promoter Name"])?.count ?? 0;
      return (
        Object.entries(columnSearch).every(([key, query]) => !query.trim() || (project[key] ?? "").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) &&
        (!projectNames.length || projectNames.includes(project["Project Name"])) &&
        (!districts.length || districts.includes(project.District)) &&
        (!builders.length || builders.includes(project.Builder)) &&
        (!promoters.length || promoters.includes(project["Promoter Name"])) &&
        (!talukas.length || talukas.includes(project.Taluka)) &&
        (!types.length || types.includes(project["Project Type"])) &&
        (!hasUpdate || project["Has Quarterly Update"] === "Yes") &&
        (!hasComplaints || complaintCount > 0 || promoterCount > 0) &&
        (!minimumUnits || (units !== null && units >= Number(minimumUnits))) &&
        (!maximumUnits || (units !== null && units <= Number(maximumUnits))) &&
        dateInRange(project["Proposed Completion Date"] || "", completionStart, completionEnd) &&
        dateInRange(project["Approved On"] || "", approvalStart, approvalEnd)
      );
    });
    rows.sort((a, b) => {
      const av = extraValue(a, sort.key, projectComplaints, promoterComplaints);
      const bv = extraValue(b, sort.key, projectComplaints, promoterComplaints);
      const missingA = av === null || av === "NA" || av === "";
      const missingB = bv === null || bv === "NA" || bv === "";
      if (missingA || missingB) return missingA === missingB ? 0 : missingA ? 1 : -1;
      const an = typeof av === "number" ? av : numeric(String(av));
      const bn = typeof bv === "number" ? bv : numeric(String(bv));
      const compared = an !== null && bn !== null ? an - bn : String(av).localeCompare(String(bv));
      return sort.direction === "asc" ? compared : -compared;
    });
    return rows;
  }, [projects, columnSearch, projectNames, districts, builders, promoters, talukas, types, completionStart, completionEnd, approvalStart, approvalEnd, minimumUnits, maximumUnits, hasUpdate, hasComplaints, sort, projectComplaints, promoterComplaints]);

  const stats = useMemo(() => inventoryStats(filtered), [filtered]);
  const datedStats = useMemo(
    () => reportingPeriods.filter(period => period.suffix !== "Q2_FY26-27").map(period => ({
      label: period.label,
      projects: projectCountForPeriod(filtered, period.suffix),
      ...quarterlyInventoryStats(filtered, period.suffix),
    })),
    [filtered],
  );
  const shares = inventoryShares(stats);
  const history = (key: "projects" | "inventory" | "unknownInventory" | "booked" | "unsold") =>
    datedStats.map(period => ({
      label: period.label,
      value: (period[key] ?? 0).toLocaleString("en-IN"),
      percentage: key === "inventory" || key === "projects" ? null : inventoryShares(period)[key],
    }));

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const pins = useMemo(() => {
    const plotted: MapPin[] = [];
    for (const project of filtered) {
      const lat = numeric(project.Latitude);
      const lng = numeric(project.Longitude);
      if (lat === null || lng === null || lat < 12.4 || lat > 13.6 || lng < 77 || lng > 78.1) continue;
      const booking = latestBooking(project);
      const units = totalUnits(project);
      plotted.push({
        id: project["Registration Number"],
        name: project["Project Name"] || "Untitled project",
        lat,
        lng,
        taluk: project.Taluka || "",
        type: project["Project Type"] || "",
        builder: project.Builder || "",
        units,
        booked: booking?.booked ?? null,
        unsold: booking?.available ?? null,
        quarter: booking?.quarter ?? "",
        pct: booking && units && units > 0 ? (booking.booked / units) * 100 : null,
        complaints: lookupName(projectComplaints, project["Project Name"])?.count ?? 0,
        promoterComplaints: lookupName(promoterComplaints, project["Promoter Name"])?.count ?? 0,
      });
    }
    return plotted;
  }, [filtered, projectComplaints, promoterComplaints]);
  const filterCount = projectNames.length + districts.length + builders.length + promoters.length + talukas.length + types.length + Number(hasUpdate) + Number(hasComplaints);
  const selected = projects.find(project => project["Registration Number"] === selectedId) ?? null;

  const clear = () => {
    setProjectNames([]);
    setDistricts([]);
    setBuilders([]);
    setPromoters([]);
    setTalukas([]);
    setTypes([]);
    setCompletionStart("");
    setCompletionEnd("");
    setApprovalStart("");
    setApprovalEnd("");
    setMinimumUnits("");
    setMaximumUnits("");
    setHasUpdate(false);
    setHasComplaints(false);
    setColumnSearch({});
    setPage(0);
  };
  const sortBy = (key: string) => {
    setSort(current => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
    setPage(0);
  };
  const moveColumn = (target: string) => {
    if (!draggedColumn || draggedColumn === target) return;
    setColumnOrder(current => {
      const from = current.findIndex(([key]) => key === draggedColumn);
      const to = current.findIndex(([key]) => key === target);
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
    setDraggedColumn(null);
  };
  const selectProjects = useCallback((names: string[]) => {
    setProjectNames(names);
    setPage(0);
  }, []);

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">Bengaluru Urban · K-RERA scrape (units + parking QPR)</p>
          <h1>BLR Real Estate <em>Sales Analysis</em></h1>
        </div>
        <button className="filter-toggle" type="button" onClick={() => setFiltersOpen(open => !open)}>
          {filtersOpen ? "Close filters" : "Filters"} <b>{filterCount}</b>
        </button>
      </header>

      <section className="metrics">
        <Metric label="Projects" value={filtered.length.toLocaleString("en-IN")} history={history("projects")} description="Filtered approvals" />
        <Metric label="Inventory" value={stats.inventory.toLocaleString("en-IN")} history={history("inventory")} description="Units in the filtered set" />
        <Metric label="Sales data not published" value={stats.unknownInventory.toLocaleString("en-IN")} percentage={shares.unknownInventory} history={history("unknownInventory")} description="Units · sales status unknown" status="unknown" />
        <Metric label="Sold" value={(stats.booked ?? 0).toLocaleString("en-IN")} percentage={shares.booked} history={history("booked")} description="Published booked units" status="booked" />
        <Metric label="Unsold inventory (available)" value={(stats.unsold ?? 0).toLocaleString("en-IN")} percentage={shares.unsold} history={history("unsold")} description="Published available units" status="unsold" />
      </section>
      <p className="metric-note">
        Headline Sold/Unsold use unit quarterly filings from the same scrape as krera.py (data/details). Project drawer also shows parking supply/booked/available when that project is in your snapshot reports. Refresh the site after scrape via explorer/scripts/refresh_public_data.py or krera.py report (auto-sync). Complaint counts are live from K-RERA complaint indexes.
      </p>

      <div className="workspace">
        <div className="side-stack">
        <aside className={filtersOpen ? "sidebar open" : "sidebar"}>
          <div className="filter-head">
            <h2>Refine the view</h2>
            <div className="filter-actions">
              <button type="button" onClick={clear}>Reset</button>
              <button className="filter-apply" type="button" onClick={() => setFiltersOpen(false)}>Apply</button>
            </div>
          </div>
          <fieldset className="filter">
            <legend>Approved on date</legend>
            <div className="dates">
              <input type="date" value={approvalStart} onChange={event => { setApprovalStart(event.target.value); setPage(0); }} />
              <input type="date" value={approvalEnd} onChange={event => { setApprovalEnd(event.target.value); setPage(0); }} />
            </div>
          </fieldset>
          <fieldset className="filter">
            <legend>Completion on date</legend>
            <div className="dates">
              <input type="date" value={completionStart} onChange={event => { setCompletionStart(event.target.value); setPage(0); }} />
              <input type="date" value={completionEnd} onChange={event => { setCompletionEnd(event.target.value); setPage(0); }} />
            </div>
          </fieldset>
          <fieldset className="filter">
            <legend>Total units {unitsBounds && <span>{unitsBounds[0].toLocaleString("en-IN")} – {unitsBounds[1].toLocaleString("en-IN")}</span>}</legend>
            <div className="unit-fields">
              <input type="number" value={minimumUnits} placeholder="Minimum" onChange={event => { setMinimumUnits(event.target.value); setPage(0); }} />
              <input type="number" value={maximumUnits} placeholder="Maximum" onChange={event => { setMaximumUnits(event.target.value); setPage(0); }} />
            </div>
          </fieldset>
          <MultiSelect label="District" options={filterOptions.District ?? []} selected={districts} setSelected={value => { setDistricts(value); setPage(0); }} />
          <MultiSelect label="Taluk" options={filterOptions.Taluka ?? []} selected={talukas} setSelected={value => { setTalukas(value); setPage(0); }} />
          <MultiSelect label="Builder" options={filterOptions.Builder ?? []} selected={builders} setSelected={value => { setBuilders(value); setPage(0); }} />
          <MultiSelect label="Promoter" options={filterOptions["Promoter Name"] ?? []} selected={promoters} setSelected={value => { setPromoters(value); setPage(0); }} />
          <MultiSelect label="Project Name" options={filterOptions["Project Name"] ?? []} selected={projectNames} setSelected={selectProjects} />
          <MultiSelect label="Project type" options={filterOptions["Project Type"] ?? []} selected={types} setSelected={value => { setTypes(value); setPage(0); }} />
          <label className="switch">
            <input type="checkbox" checked={hasUpdate} onChange={event => { setHasUpdate(event.target.checked); setPage(0); }} />
            Has latest quarterly update
          </label>
          <label className="switch">
            <input type="checkbox" checked={hasComplaints} onChange={event => { setHasComplaints(event.target.checked); setPage(0); }} />
            Has K-RERA complaints
          </label>
        </aside>
        <ProjectMap
          pins={pins}
          filteredCount={filtered.length}
          selectedId={selectedId}
          onOpen={id => { setComplaintFocus(null); setSelectedId(id); }}
        />
        </div>

        <section className="table-panel">
          <div className="table-meta">
            <span>{filtered.length ? `${(currentPage * PAGE_SIZE + 1).toLocaleString("en-IN")}–${Math.min((currentPage + 1) * PAGE_SIZE, filtered.length).toLocaleString("en-IN")} of ${filtered.length.toLocaleString("en-IN")} projects` : "0 matching projects"}</span>
            <span>Drag headings to reorder · Drag edges to resize · Click a complaint count for the case list · * Earlier report used where the labelled period is missing</span>
          </div>
          <div className="table-wrap">
            <table style={{ width: columnOrder.reduce((sum, [key]) => sum + (columnWidths[key] ?? defaultColumnWidth(key)), 0) }}>
              <colgroup>
                {columnOrder.map(([key]) => <col key={key} style={{ width: columnWidths[key] ?? defaultColumnWidth(key) }} />)}
              </colgroup>
              <thead>
                <tr>
                  {columnOrder.map(([key, label]) => (
                    <th
                      key={key}
                      draggable
                      onDragStart={() => setDraggedColumn(key)}
                      onDragOver={event => event.preventDefault()}
                      onDrop={() => moveColumn(key)}
                      onDragEnd={() => setDraggedColumn(null)}
                      className={draggedColumn === key ? "dragging" : ""}
                      style={{ position: "sticky" }}
                    >
                      <button className="head" type="button" onClick={() => sortBy(key)}>
                        <span className="drag-handle">⠿</span>
                        {label} <i className={sort.key === key ? "active" : ""}>{sort.key === key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</i>
                      </button>
                      {columnSearchFields[key] && (
                        <input
                          className="column-search"
                          value={columnSearch[key] ?? ""}
                          placeholder={columnSearchFields[key]}
                          onChange={event => {
                            setColumnSearch(current => ({ ...current, [key]: event.target.value }));
                            setPage(0);
                          }}
                          onDragStart={event => event.preventDefault()}
                        />
                      )}
                      <span
                        className="column-resize"
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize ${label}`}
                        onPointerDown={event => {
                          dragOrigin.current = { key, x: event.clientX, width: columnWidths[key] ?? defaultColumnWidth(key) };
                          event.currentTarget.setPointerCapture(event.pointerId);
                        }}
                        onPointerMove={event => {
                          const origin = dragOrigin.current;
                          if (!origin || origin.key !== key) return;
                          const next = Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, origin.width + event.clientX - origin.x));
                          setColumnWidths(current => ({ ...current, [key]: next }));
                        }}
                        onPointerUp={() => {
                          dragOrigin.current = null;
                        }}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map(project => (
                  <ProjectRow
                    key={project["Registration Number"]}
                    project={project}
                    columnOrder={columnOrder}
                    selected={project["Registration Number"] === selectedId}
                    complaintCount={lookupName(projectComplaints, project["Project Name"])?.count ?? 0}
                    promoterCount={lookupName(promoterComplaints, project["Promoter Name"])?.count ?? 0}
                    onOpen={() => { setComplaintFocus(null); setSelectedId(project["Registration Number"]); }}
                    onOpenComplaints={kind => { setComplaintFocus(kind); setSelectedId(project["Registration Number"]); }}
                  />
                ))}
              </tbody>
            </table>
            {!projects.length && <p className="loading">Loading RERA project data…</p>}
            {projects.length > 0 && !filtered.length && <p className="loading">No projects match these filters.</p>}
          </div>
          {filtered.length > PAGE_SIZE && (
            <div className="pagination">
              <button type="button" onClick={() => setPage(currentPage - 1)} disabled={currentPage === 0}>Previous</button>
              <span>Page {currentPage + 1} of {pageCount}</span>
              <button type="button" onClick={() => setPage(currentPage + 1)} disabled={currentPage === pageCount - 1}>Next</button>
            </div>
          )}
        </section>
      </div>

      {selected && (
        <DetailDrawer
          project={selected}
          projectComplaint={lookupName(projectComplaints, selected["Project Name"])}
          promoterComplaint={lookupName(promoterComplaints, selected["Promoter Name"])}
          orders={orders}
          focus={complaintFocus}
          onClose={() => { setSelectedId(null); setComplaintFocus(null); }}
        />
      )}
    </main>
  );
}

const ProjectRow = memo(function ProjectRow({
  project,
  columnOrder,
  selected,
  complaintCount,
  promoterCount,
  onOpen,
  onOpenComplaints,
}: {
  project: Project;
  columnOrder: Column[];
  selected: boolean;
  complaintCount: number;
  promoterCount: number;
  onOpen: () => void;
  onOpenComplaints: (kind: "project" | "promoter") => void;
}) {
  const booking = latestBooking(project);
  const surveys = extractSurveys(project["Project Address"]);
  const mapLat = numeric(project.Latitude);
  const mapLng = numeric(project.Longitude);
  const mapUrl = mapLat !== null && mapLng !== null ? `https://www.google.com/maps?q=${mapLat},${mapLng}` : null;
  return (
    <tr className={selected ? "selected" : ""}>
      {columnOrder.map(([key]) => {
        if (key === "complaints" || key === "promoterComplaints") {
          const count = key === "complaints" ? complaintCount : promoterCount;
          const kind = key === "complaints" ? "project" : "promoter";
          return (
            <td key={key}>
              {count ? (
                <button className="count-btn" type="button" onClick={() => onOpenComplaints(kind)} title="Show complaint details">{count}</button>
              ) : (
                <span className="count-btn zero">0</span>
              )}
            </td>
          );
        }
        if (key === "surveys") {
          const label = surveys.length ? surveys.slice(0, 2).map(hit => hit.number).join(", ") + (surveys.length > 2 ? ` +${surveys.length - 2}` : "") : "—";
          return <td key={key} title={surveys.map(hit => hit.clause).join("; ")}>{label}</td>;
        }
        const cell = value(project, key);
        const isMarch = key.endsWith("(Q4_FY25-26)");
        const isQuarterCount = key.startsWith("Units Booked (") || key.startsWith("Units Available (");
        const cellBooking = isMarch ? bookingForPeriod(project, "Q4_FY25-26") : key.endsWith("(Q3_FY25-26)") ? bookingForPeriod(project, "Q3_FY25-26") : booking;
        const hasFallback = cell !== null && (isQuarterCount || key === "bookedPercent") && Boolean(cellBooking?.fallback);
        const title = key === "Total Units"
          ? booking && booking.available !== null
            ? `${booking.quarter}: ${booking.booked} booked + ${booking.available} available = ${cell} units`
            : "Project-details inventory; a complete quarterly booked/available pair is unavailable"
          : hasFallback
            ? `${cellBooking?.quarter} used because ${isMarch ? "Mar" : "Jun"} 2026 is unavailable`
            : String(cell ?? "—");
        return (
          <td key={key} title={title}>
            {key === "Project Name" ? (
              <>
                <button className="name-btn" type="button" onClick={onOpen}>{cell ?? "—"}</button>
                {mapUrl && <a className="map-link" href={mapUrl} target="_blank" rel="noreferrer">Map</a>}
              </>
            ) : key === "Has Quarterly Update" ? (
              <span className={cell === "Yes" ? "tag yes" : "tag"}>{cell === "Yes" ? "Yes" : "No"}</span>
            ) : key === "bookedPercent" ? (
              cell === null ? "—" : <span className="fill" style={{ ["--fill" as string]: `${Math.max(0, Math.min(100, cell as number))}%` }}><b>{(cell as number).toFixed(1)}%{hasFallback ? "*" : ""}</b></span>
            ) : isQuarterCount ? (
              <>{cell ?? "—"}{hasFallback ? "*" : ""}</>
            ) : (
              cell ?? "—"
            )}
          </td>
        );
      })}
    </tr>
  );
});
