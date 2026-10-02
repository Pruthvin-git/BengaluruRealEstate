"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, MarkerClusterGroup } from "leaflet";
import "leaflet/dist/leaflet.css";

export type MapPin = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  taluk: string;
  type: string;
  builder: string;
  units: number | null;
  booked: number | null;
  unsold: number | null;
  quarter: string;
  pct: number | null;
  complaints: number;
  promoterComplaints: number;
};

const CITY: [[number, number], [number, number]] = [[12.58, 77.22], [13.42, 77.92]];

function esc(value: string) {
  return value.replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] ?? char);
}

function num(value: number | null) {
  return value === null ? "—" : value.toLocaleString("en-IN");
}

function popupHtml(pin: MapPin) {
  return `<article class="pin-card">
    <strong>${esc(pin.name)}</strong>
    <p>${esc(pin.taluk || "—")} · ${esc(pin.type || "—")}</p>
    <p>${esc(pin.builder || "—")}</p>
    <dl>
      <div><dt>Units</dt><dd>${num(pin.units)}</dd></div>
      <div><dt>Booked${pin.quarter ? ` · ${esc(pin.quarter)}` : ""}</dt><dd>${num(pin.booked)}${pin.pct === null ? "" : ` · ${pin.pct.toFixed(0)}%`}</dd></div>
      <div><dt>Unsold</dt><dd>${num(pin.unsold)}</dd></div>
      <div><dt>Complaints</dt><dd>${pin.complaints.toLocaleString("en-IN")} project · ${pin.promoterComplaints.toLocaleString("en-IN")} promoter</dd></div>
    </dl>
    <button type="button" class="map-open" data-id="${esc(pin.id)}">Open details</button>
  </article>`;
}

export function ProjectMap({
  pins,
  filteredCount,
  selectedId,
  onOpen,
}: {
  pins: MapPin[];
  filteredCount: number;
  selectedId: string | null;
  onOpen: (id: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const groupRef = useRef<MarkerClusterGroup | null>(null);
  const signatureRef = useRef("");
  const openRef = useRef(onOpen);
  const [showNames, setShowNames] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const missing = Math.max(0, filteredCount - pins.length);
  openRef.current = onOpen;

  useEffect(() => {
    setShowNames(pins.length > 0 && pins.length <= 40);
  }, [pins.length]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const frame = requestAnimationFrame(() => mapRef.current?.invalidateSize());
    return () => cancelAnimationFrame(frame);
  }, [expanded]);

  useEffect(() => {
    let cancelled = false;
    const hostNode = host.current;
    if (!hostNode) return;

    (async () => {
      const leaflet = await import("leaflet");
      await import("leaflet.markercluster");
      if (cancelled || !host.current) return;
      const L = (leaflet.default ?? leaflet) as typeof leaflet.default;
      if (!mapRef.current) {
        const map = L.map(host.current, { scrollWheelZoom: true, zoomControl: true });
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
        }).addTo(map);
        const city = L.latLngBounds(CITY[0], CITY[1]);
        map.fitBounds(city, { padding: [12, 12] });
        map.setMaxBounds(city.pad(0.45));
        map.on("popupopen", event => {
          const button = event.popup.getElement()?.querySelector<HTMLButtonElement>(".map-open");
          button?.addEventListener("click", () => {
            const id = button.dataset.id;
            if (id) openRef.current(id);
          });
        });
        mapRef.current = map;
        requestAnimationFrame(() => map.invalidateSize());
      }

      const map = mapRef.current;
      if (groupRef.current) {
        map.removeLayer(groupRef.current);
        groupRef.current = null;
      }
      const group = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 42,
        spiderfyOnMaxZoom: true,
        iconCreateFunction: cluster => L.divIcon({
          className: "pin-cluster",
          html: `<span>${cluster.getChildCount().toLocaleString("en-IN")}</span>`,
          iconSize: [40, 40],
        }),
      });
      const signature = pins.map(pin => pin.id).join("|");
      const refit = signature !== signatureRef.current;
      signatureRef.current = signature;
      for (const pin of pins) {
        const marker = L.marker([pin.lat, pin.lng], {
          icon: L.divIcon({
            className: `pin${pin.complaints > 0 ? " pin-alert" : ""}`,
            html: "<span></span>",
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          }),
          title: pin.name,
        });
        marker.bindTooltip(esc(pin.name), {
          permanent: showNames,
          direction: "top",
          offset: [0, -8],
          className: "pin-tip",
          opacity: 1,
        });
        marker.bindPopup(popupHtml(pin), { maxWidth: 280, minWidth: 220, className: "pin-popup" });
        group.addLayer(marker);
      }
      map.addLayer(group);
      groupRef.current = group;
      if (refit) {
        if (pins.length) {
          const bounds = group.getBounds();
          if (bounds.isValid()) map.fitBounds(bounds.pad(0.12), { padding: [18, 18], maxZoom: 12 });
        } else {
          map.fitBounds(L.latLngBounds(CITY[0], CITY[1]), { padding: [12, 12] });
        }
      }
      requestAnimationFrame(() => map.invalidateSize());
    })().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [pins, showNames]);

  useEffect(() => () => {
    mapRef.current?.remove();
    mapRef.current = null;
    groupRef.current = null;
  }, []);

  return (
    <>
    {expanded && <div className="map-placeholder" aria-hidden="true" />}
    <section className={expanded ? "map-card expanded" : "map-card"} aria-label="Bengaluru project map" data-selected={selectedId ?? ""}>
      <div className="map-head">
        <div>
          <h2>On the map</h2>
          <p>{pins.length.toLocaleString("en-IN")} of {filteredCount.toLocaleString("en-IN")} filtered projects are plotted. {missing ? `${missing.toLocaleString("en-IN")} have no coordinates.` : "Every filtered project has a pin."}</p>
        </div>
        <label className="map-names">
          <input type="checkbox" checked={showNames} onChange={event => setShowNames(event.target.checked)} />
          Names
        </label>
      </div>
      <div className="map-legend">
        <span><i className="swatch sold" /> Sales reported</span>
        <span><i className="swatch alert" /> Has complaints</span>
        <span>Hover a pin for the name. Click it for units, bookings, and complaints.</span>
      </div>
      <div className="map-frame">
        <div ref={host} className="map-canvas" />
        <button type="button" className="map-size" aria-label={expanded ? "Minimize map" : "Maximize map"} onClick={() => setExpanded(open => !open)}>
          {expanded ? (
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3 8h10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M9 2h5v5M14 2 9 7M7 14H2V9M2 14l5-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          )}
        </button>
      </div>
    </section>
    </>
  );
}
