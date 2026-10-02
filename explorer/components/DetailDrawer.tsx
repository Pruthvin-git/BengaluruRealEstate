"use client";

import { useEffect, useState } from "react";
import { extractSurveys, judgmentQuery, type SurveyHit } from "../lib/survey";
import { normName, type NamedCount } from "../lib/names";
import {
  bookingForPeriod,
  latestBooking,
  numeric,
  totalUnits,
  type Project,
} from "../lib/project-metrics";

export type OrderRow = {
  complaintNo: string;
  complaintDate: string;
  orderDate: string;
  petitioner: string;
  respondent: string;
  project: string;
  promoter: string;
  district: string;
  relief: string;
  judgementBy: string;
  bench: string;
  orderHref: string;
};

type ComplaintRow = {
  complaintNo: string;
  promoter: string;
  project: string;
  complainant: string;
  status: string;
  complaintDate: string;
  disposedDate: string;
  proceedingHref: string;
  orderHref: string;
};

type CaseHit = { title: string; url: string; snippet: string };

const money = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : value.toLocaleString("en-IN");

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value || "—"}</b>
    </div>
  );
}

function ComplaintTable({ rows, empty }: { rows: ComplaintRow[] | null; empty: string }) {
  if (rows === null) return <p className="muted">Loading complaints from K-RERA…</p>;
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <table className="mini">
      <thead>
        <tr>
          <th>No.</th>
          <th>Status</th>
          <th>By</th>
          <th>Filed</th>
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 40).map(row => (
          <tr key={row.complaintNo + row.complaintDate}>
            <td>{row.proceedingHref ? <a href={row.proceedingHref} target="_blank" rel="noreferrer">{row.complaintNo}</a> : row.complaintNo}{row.orderHref ? <> · <a href={row.orderHref} target="_blank" rel="noreferrer">Order</a></> : null}</td>
            <td>{row.status || "—"}</td>
            <td>{row.complainant || "—"}</td>
            <td>{row.complaintDate || "—"}{row.disposedDate ? ` · ${row.disposedDate}` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DetailDrawer({
  project,
  projectComplaint,
  promoterComplaint,
  orders,
  focus,
  onClose,
}: {
  project: Project;
  projectComplaint: NamedCount | null;
  promoterComplaint: NamedCount | null;
  orders: OrderRow[];
  focus: "project" | "promoter" | null;
  onClose: () => void;
}) {
  const surveys = extractSurveys(project["Project Address"]);
  const [projectRows, setProjectRows] = useState<ComplaintRow[] | null>(projectComplaint ? null : []);
  const [promoterRows, setPromoterRows] = useState<ComplaintRow[] | null>(promoterComplaint ? null : []);
  const [cases, setCases] = useState<Record<string, { results: CaseHit[]; note?: string; searchUrl: string; error?: string }>>({});
  const [searching, setSearching] = useState(false);
  const [land, setLand] = useState<string[] | null>(null);
  const [landState, setLandState] = useState<"idle" | "loading" | "done" | "error">("idle");

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (!focus) return;
    const sameList = promoterComplaint?.href && promoterComplaint.href === projectComplaint?.href;
    const id = focus === "promoter" && !sameList ? "complaint-promoter" : "complaint-project";
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focus, project, projectRows, promoterRows, projectComplaint, promoterComplaint]);

  useEffect(() => {
    let cancel = false;
    async function load(href: string | undefined, setRows: (rows: ComplaintRow[]) => void) {
      if (!href) {
        setRows([]);
        return;
      }
      try {
        const response = await fetch(`/api/complaints?href=${encodeURIComponent(href)}`);
        const body = await response.json();
        if (!cancel) setRows(body.rows ?? []);
      } catch {
        if (!cancel) setRows([]);
      }
    }
    setProjectRows(projectComplaint ? null : []);
    setPromoterRows(promoterComplaint ? null : []);
    load(projectComplaint?.href, setProjectRows);
    if (promoterComplaint?.href && promoterComplaint.href !== projectComplaint?.href) {
      load(promoterComplaint.href, setPromoterRows);
    } else if (!promoterComplaint) setPromoterRows([]);
    else setPromoterRows([]);
    return () => {
      cancel = true;
    };
  }, [project, projectComplaint, promoterComplaint]);

  const booking = latestBooking(project);
  const units = totalUnits(project);
  const mapLat = numeric(project.Latitude);
  const mapLng = numeric(project.Longitude);
  const mapUrl = mapLat !== null && mapLng !== null ? `https://www.google.com/maps?q=${mapLat},${mapLng}` : null;
  const projectKey = normName(project["Project Name"]);
  const promoterKey = normName(project["Promoter Name"]);
  const projectOrders = orders.filter(order => {
    const orderProject = normName(order.project);
    const orderPromoter = normName(order.promoter);
    const sameProject = projectKey.length >= 8 && orderProject.length >= 8 && (orderProject === projectKey || orderProject.includes(projectKey) || projectKey.includes(orderProject));
    const samePromoter = promoterKey.length >= 8 && orderPromoter === promoterKey;
    return sameProject || samePromoter;
  }).slice(0, 25);

  async function searchCases() {
    const picks = surveys.slice(0, 2);
    if (!picks.length) return;
    setSearching(true);
    const next: typeof cases = {};
    for (const hit of picks) {
      const query = judgmentQuery(hit, project.District, project.Taluka);
      const response = await fetch(`/api/cases?q=${encodeURIComponent(query)}`);
      next[hit.number] = await response.json();
    }
    setCases(next);
    setSearching(false);
  }

  async function loadLand() {
    const action = project["Action ID"];
    if (!action) return;
    setLandState("loading");
    try {
      const response = await fetch(`/api/land?action=${encodeURIComponent(action)}`);
      const body = await response.json();
      setLand(body.clauses ?? []);
      setLandState("done");
    } catch {
      setLandState("error");
    }
  }

  return (
    <>
      <button className="drawer-back" type="button" aria-label="Close project details" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={project["Project Name"]}>
        <button className="close" type="button" onClick={onClose}>Close</button>
        <p className="kicker">{project["Registration Number"]}</p>
        <h2>{project["Project Name"]}</h2>
        <p className="muted">
          {project.Builder} · {project["Promoter Name"]}
          {mapUrl && <> · <a className="map-link" href={mapUrl} target="_blank" rel="noreferrer">Map</a></>}
        </p>
        <p className="muted">{project["Project Address"]}</p>
        <div className="facts">
          <Fact label="Approved" value={project["Approved On"]} />
          <Fact label="Completion" value={project["Proposed Completion Date"]} />
          <Fact label="Total units" value={money(units)} />
          <Fact label="Booked" value={booking ? `${money(booking.booked)} · ${booking.quarter}${booking.fallback ? "*" : ""}` : "—"} />
          <Fact label="Unsold" value={money(booking?.available ?? null)} />
          <Fact label="District" value={`${project.District} · ${project.Taluka}`} />
        </div>

        <h3>Complaints</h3>
        <p className="muted">
          Public K-RERA lists. Project complaints are grievances naming this project. Promoter complaints count every project filed against {project["Promoter Name"] || "this promoter"}.
        </p>
        <div className="actions">
          {projectComplaint && <a href={projectComplaint.href} target="_blank" rel="noreferrer">Project list ({projectComplaint.count})</a>}
          {promoterComplaint && <a href={promoterComplaint.href} target="_blank" rel="noreferrer">Promoter list ({promoterComplaint.count})</a>}
          {!projectComplaint && !promoterComplaint && <span className="muted">No K-RERA complaint index hit for this name.</span>}
        </div>
        <section id="complaint-project" className={focus === "project" || (focus === "promoter" && promoterComplaint?.href === projectComplaint?.href) ? "section-hot" : undefined}>
          <h3>Against this project</h3>
          <p className="muted">Each row is the public K-RERA filing. The complaint number opens the proceeding, and Order opens the published PDF.</p>
          <ComplaintTable rows={projectRows} empty="No complaint rows published for this project name." />
        </section>
        {promoterComplaint && promoterComplaint.href !== projectComplaint?.href && (
          <section id="complaint-promoter" className={focus === "promoter" ? "section-hot" : undefined}>
            <h3>Against this promoter</h3>
            <p className="muted">Filings against {project["Promoter Name"] || "this promoter"} across projects. The complaint number opens the proceeding.</p>
            <ComplaintTable rows={promoterRows} empty="No promoter complaint rows loaded." />
          </section>
        )}

        <h3>Authority orders</h3>
        {!projectOrders.length && <p className="muted">No published authority order in the local index names this project or promoter.</p>}
        {projectOrders.map(order => (
          <div className="case" key={order.complaintNo + order.orderDate}>
            <b>{order.orderHref ? <a href={order.orderHref} target="_blank" rel="noreferrer">{order.complaintNo}</a> : order.complaintNo} · {order.project}</b>
            <span className="muted">{order.petitioner} vs {order.respondent}. {order.complaintDate} → {order.orderDate || "pending"}. {order.bench}</span>
            {order.relief && <div>{order.relief}</div>}
          </div>
        ))}

        <h3>Survey numbers and court cases</h3>
        <p className="muted">
          Survey numbers are read from the project address. Revenue-court cases on rccms.karnataka.gov.in need a captcha plus district, taluk, hobli, and village, so they cannot be pulled in automatically. Published High Court judgments can be searched.
        </p>
        <div className="chips">
          {surveys.length ? surveys.map((hit: SurveyHit) => (
            <span key={hit.number}>{hit.number}{hit.village ? ` · ${hit.village}` : ""}</span>
          )) : <span>No survey number in the address</span>}
        </div>
        <div className="actions">
          <button className="solid" type="button" disabled={!surveys.length || searching} onClick={searchCases}>
            {searching ? "Searching judgments…" : "Search Karnataka judgments"}
          </button>
          <button type="button" onClick={loadLand} disabled={landState === "loading" || !project["Action ID"]}>
            {landState === "loading" ? "Reading K-RERA…" : "Read survey text from K-RERA"}
          </button>
          <a href="https://rccms.karnataka.gov.in/" target="_blank" rel="noreferrer">RCCMS survey search</a>
          <a href="https://services.ecourts.gov.in/ecourtindia_v6/" target="_blank" rel="noreferrer">eCourts</a>
        </div>
        {landState === "done" && (
          <p className="muted">{land?.length ? land.join(" · ") : "The K-RERA detail page did not show a survey-number line."}</p>
        )}
        {landState === "error" && <p className="muted">K-RERA detail page could not be read.</p>}
        {Object.entries(cases).map(([number, block]) => (
          <div key={number}>
            <h3>Judgments mentioning survey {number}</h3>
            <p className="muted">{block.note || block.error} <a href={block.searchUrl} target="_blank" rel="noreferrer">Open search</a></p>
            {!block.results?.length && <p className="muted">No published judgment matched this wording.</p>}
            {block.results?.map(hit => (
              <div className="case" key={hit.url}>
                <b><a href={hit.url} target="_blank" rel="noreferrer">{hit.title}</a></b>
                {hit.snippet && <span className="muted">{hit.snippet}</span>}
              </div>
            ))}
          </div>
        ))}
        <div className="facts" style={{ marginTop: 18 }}>
          <Fact label="Dec 2025 booked" value={money(bookingForPeriod(project, "Q3_FY25-26")?.booked ?? null)} />
          <Fact label="Mar 2026 booked" value={money(bookingForPeriod(project, "Q4_FY25-26")?.booked ?? null)} />
        </div>
      </aside>
    </>
  );
}
