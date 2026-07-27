import React, { useState, useMemo, useEffect, useCallback } from "react";
import { apiGet, apiDelete } from "../lib/api";
import { colors, radius, shadows, fonts, transitions } from "../tokens";
import { Icon, FileGlyph, Pill, IconBtn, Btn, SegmentedControl, FilterChip, GroupHeader, EmptyState } from "./shared";

// ─────────────────────────────────────────────────────────────────────────────
// Resource row (list view)
// ─────────────────────────────────────────────────────────────────────────────
function ResourceRow({ resource, onDelete }) {
  const [hover, setHover] = useState(false);
  const r = resource;
  const fileType = r.resource_type === "link" ? "link" : (r.file_type || "pdf");
  const displayDate = r.created_at
    ? new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : "";
  const displaySize = r.file_size ? formatFileSize(r.file_size) : (r.resource_type === "link" ? "—" : "");
  const displayName = r.resource_type === "file"
    ? (r.original_filename || "")
    : (r.source_name || extractDomain(r.url) || r.url || "");

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto auto",
        alignItems: "center", gap: 14,
        padding: "12px 14px",
        background: hover ? colors.gray50 : colors.white,
        borderTop: `1px solid ${colors.border}`,
        transition: "background .12s",
      }}>
      <FileGlyph type={fileType} size={36} />
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 13.5, fontWeight: 600, color: colors.gray900,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {r.resource_type === "link" ? (
              <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "inherit", textDecoration: "none" }}>
                {r.title} <Icon name="box-arrow-up-right" style={{ fontSize: "0.7em" }} />
              </a>
            ) : r.title}
          </span>
          {r.category && <Pill>{r.category}</Pill>}
        </div>
        <div style={{
          fontSize: 11.5, color: colors.gray500, marginTop: 2,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          fontFamily: fonts.mono,
        }}>
          {displayName}
        </div>
      </div>
      <div style={{ fontSize: 11.5, color: colors.gray500, textAlign: "right", whiteSpace: "nowrap" }}>
        {displayDate}
      </div>
      <div style={{
        fontSize: 11.5, color: colors.gray500, textAlign: "right",
        width: 64, whiteSpace: "nowrap", fontFamily: fonts.mono,
      }}>
        {displaySize}
      </div>
      <div style={{ display: "flex", gap: 2, opacity: hover ? 1 : 0.55, transition: "opacity .12s" }}>
        {r.resource_type === "file" && (
          <>
            <IconBtn icon="eye" label="Preview" onClick={() => window.open(`/companies/resources/${r.id}/viewer`, "_blank")} />
            <IconBtn icon="download" label="Download" onClick={() => { window.location.href = `/companies/api/resources/${r.id}/download`; }} />
          </>
        )}
        {r.resource_type === "link" && (
          <IconBtn icon="box-arrow-up-right" label="Open link" onClick={() => window.open(r.url, "_blank", "noopener,noreferrer")} />
        )}
        <IconBtn icon="trash" label="Delete" danger onClick={() => onDelete(r.id)} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Resource card (grid view)
// ─────────────────────────────────────────────────────────────────────────────
function ResourceCard({ resource, onDelete }) {
  const [hover, setHover] = useState(false);
  const r = resource;
  const fileType = r.resource_type === "link" ? "link" : (r.file_type || "pdf");
  const displayDate = r.created_at
    ? new Date(r.created_at).toLocaleDateString("en-US", { month: "short", year: "numeric" })
    : "";
  const displaySize = r.file_size ? formatFileSize(r.file_size) : (r.resource_type === "link" ? "—" : "");
  const displayName = r.resource_type === "file"
    ? (r.original_filename || "")
    : (r.source_name || extractDomain(r.url) || "");

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: colors.white,
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        padding: 14,
        display: "flex", flexDirection: "column", gap: 10,
        boxShadow: hover ? "0 6px 16px rgba(15,23,42,.06)" : shadows.light,
        transform: hover ? "translateY(-1px)" : "none",
        transition: "all .15s", cursor: "pointer",
        position: "relative",
      }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <FileGlyph type={fileType} size={40} />
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {r.category && <Pill>{r.category}</Pill>}
          <IconBtn icon="trash" label="Delete" danger onClick={(e) => { e.stopPropagation(); onDelete(r.id); }} />
        </div>
      </div>
      <div style={{ minHeight: 38 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: colors.gray900, lineHeight: 1.3, marginBottom: 2 }}>
          {r.title}
        </div>
        <div style={{
          fontSize: 10.5, color: colors.gray500,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          fontFamily: fonts.mono,
        }}>
          {displayName}
        </div>
      </div>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        paddingTop: 8, borderTop: `1px solid ${colors.border}`,
        fontSize: 11, color: colors.gray500,
      }}>
        <span>{displayDate}</span>
        <span style={{ fontFamily: fonts.mono }}>{displaySize}</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function extractDomain(url) {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch { return url; }
}

function computeTotalSize(resources) {
  return resources.reduce((acc, r) => acc + (r.file_size || 0), 0);
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return days + " days ago";
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : months + " months ago";
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────
export function CompanyResourcesManager({ companyId, companyName, openUploadModal, openLinkModal }) {
  // Data
  const [resources, setResources] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // UI state
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [groupBy, setGroupBy] = useState("flat");
  const [viewMode, setViewMode] = useState("list");
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());

  // ── Fetch resources ──
  const fetchResources = useCallback(() => {
    setLoading(true);
    setError(null);
    apiGet(`/companies/api/${companyId}/resources`)
      .then((result) => {
        if (result.success) {
          setResources(result.data.resources || []);
          setCategories(result.data.categories || []);
        } else {
          setError("Failed to load resources");
        }
      })
      .catch(() => setError("Failed to load resources"))
      .finally(() => setLoading(false));
  }, [companyId]);

  useEffect(() => { fetchResources(); }, [fetchResources]);

  // Listen for changes from the vanilla JS upload/link modal
  useEffect(() => {
    const handler = () => fetchResources();
    document.addEventListener("resources-changed", handler);
    return () => document.removeEventListener("resources-changed", handler);
  }, [fetchResources]);

  // ── Delete ──
  const handleDelete = useCallback((id) => {
    if (!confirm("Delete this resource?")) return;
    apiDelete(`/companies/api/resources/${id}`)
      .then((result) => {
        if (result.success) fetchResources();
        else alert("Failed to delete resource.");
      })
      .catch(() => alert("Failed to delete."));
  }, [fetchResources]);

  // ── Derived data ──
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return resources
      .filter((r) => {
        if (activeCategory && r.category !== activeCategory) return false;
        if (q) {
          const haystack = [r.title, r.original_filename, r.category, r.source_name, r.url]
            .filter(Boolean).join(" ").toLowerCase();
          if (!haystack.includes(q)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "newest") return (b.created_at || "").localeCompare(a.created_at || "");
        if (sortBy === "oldest") return (a.created_at || "").localeCompare(b.created_at || "");
        if (sortBy === "name") return (a.title || "").localeCompare(b.title || "");
        if (sortBy === "type") return (a.resource_type || "").localeCompare(b.resource_type || "");
        return 0;
      });
  }, [resources, searchQuery, activeCategory, sortBy]);

  const groups = useMemo(() => {
    if (groupBy === "flat") return [{ key: "__all__", items: filtered }];
    const map = new Map();
    filtered.forEach((r) => {
      let key;
      if (groupBy === "year") {
        const d = r.resource_date || r.created_at;
        key = d ? new Date(d).getFullYear().toString() : "Unknown";
      } else {
        key = r.category || "Uncategorized";
      }
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(r);
    });
    const entries = [...map.entries()];
    if (groupBy === "year") entries.sort((a, b) => b[0].localeCompare(a[0]));
    else entries.sort((a, b) => a[0].localeCompare(b[0]));
    return entries.map(([key, items]) => ({ key, items }));
  }, [filtered, groupBy]);

  // Category counts (always based on all resources, not filtered)
  const categoryCounts = useMemo(() => {
    const counts = {};
    resources.forEach((r) => {
      const cat = r.category || "";
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [resources]);

  const totalSize = computeTotalSize(resources);
  const lastUpload = resources.length
    ? resources.reduce((latest, r) => (r.created_at > latest ? r.created_at : latest), "")
    : null;

  const hasFilters = searchQuery || activeCategory;

  function clearFilters() {
    setSearchQuery("");
    setActiveCategory("");
  }

  function toggleGroup(key) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // ── Loading / error states ──
  if (loading) {
    return (
      <section style={cardStyle}>
        <div style={{ padding: 48, textAlign: "center", color: colors.gray500, fontSize: 13 }}>
          <div className="spinner-border spinner-border-sm" role="status" style={{ marginRight: 8 }} />
          Loading resources...
        </div>
      </section>
    );
  }
  if (error) {
    return (
      <section style={cardStyle}>
        <div style={{ padding: 24, textAlign: "center", color: colors.danger500, fontSize: 13 }}>
          {error}
          <button onClick={fetchResources} style={{
            marginLeft: 8, border: "none", background: "transparent",
            color: colors.accent, fontWeight: 600, cursor: "pointer",
          }}>Retry</button>
        </div>
      </section>
    );
  }

  // ── Render ──
  return (
    <section style={cardStyle}>
      {/* ── HEADER ── */}
      <header style={{
        padding: "16px 18px", borderBottom: `1px solid ${colors.border}`,
        background: "linear-gradient(180deg,#fcfdfe 0%,#fff 100%)",
      }}>
        {/* Title + meta + actions */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: colors.accent50, color: colors.accent,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
            }}>
              <Icon name="folder2-open" />
            </div>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: colors.gray900, margin: 0 }}>Company Resources</h3>
              <div style={{ fontSize: 11.5, color: colors.gray500, marginTop: 1 }}>
                {resources.length} item{resources.length !== 1 ? "s" : ""}
                {totalSize > 0 && <> &middot; {formatFileSize(totalSize)}</>}
                {lastUpload && <> &middot; Last upload {timeAgo(lastUpload)}</>}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn icon="link-45deg" kind="secondary" size="sm" onClick={openLinkModal}>Save link</Btn>
            <Btn icon="cloud-upload" kind="primary" size="sm" onClick={openUploadModal}>Upload file</Btn>
          </div>
        </div>

        {/* Search + controls */}
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {/* Search */}
          <div style={{ position: "relative", flex: "1 1 280px", minWidth: 240 }}>
            <Icon name="search" style={{
              position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)",
              color: colors.gray400, fontSize: 13,
            }} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, filename, or tag\u2026"
              style={{
                width: "100%", padding: "8px 12px 8px 34px",
                border: `1px solid ${colors.border}`, borderRadius: 8,
                fontSize: 13, fontFamily: "inherit", color: colors.gray800,
                background: colors.white, outline: "none",
                boxSizing: "border-box",
              }}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} style={{
                position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                border: "none", background: colors.gray100, color: colors.gray600,
                width: 20, height: 20, borderRadius: 999, cursor: "pointer", fontSize: 11,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>&times;</button>
            )}
          </div>

          {/* Group-by */}
          <SegmentedControl
            value={groupBy}
            onChange={setGroupBy}
            options={[
              { id: "flat", label: "Flat" },
              { id: "year", label: "Year" },
              { id: "type", label: "Type" },
            ]}
          />

          {/* Sort */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Icon name="arrow-down-up" style={{ fontSize: 12, color: colors.gray500 }} />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                border: `1px solid ${colors.border}`, borderRadius: 8,
                padding: "6px 24px 6px 10px",
                fontSize: 12, fontFamily: "inherit", color: colors.gray700,
                background: colors.white, appearance: "none", cursor: "pointer",
              }}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name (A→Z)</option>
              <option value="type">Type</option>
            </select>
          </div>

          {/* View toggle */}
          <SegmentedControl
            value={viewMode}
            onChange={setViewMode}
            options={[
              { id: "list", icon: "list-ul" },
              { id: "grid", icon: "grid-3x3-gap" },
            ]}
          />
        </div>

        {/* Filter chips */}
        {categories.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 12 }}>
            <FilterChip
              label="All"
              count={resources.length}
              active={!activeCategory}
              onClick={() => setActiveCategory("")}
            />
            {categories.map((cat) => (
              <FilterChip
                key={cat}
                label={cat}
                count={categoryCounts[cat] || 0}
                active={activeCategory === cat}
                onClick={() => setActiveCategory(activeCategory === cat ? "" : cat)}
              />
            ))}
          </div>
        )}
      </header>

      {/* ── BODY ── */}
      <div style={{ background: colors.white }}>
        {filtered.length === 0 ? (
          hasFilters
            ? <EmptyState icon="search" message="No resources match these filters" action="Clear filters" onAction={clearFilters} />
            : <EmptyState icon="inbox" message="No resources yet. Upload a file or save a link to get started." />
        ) : viewMode === "grid" ? (
          groups.map((g) => (
            <div key={g.key}>
              {groupBy !== "flat" && (
                <GroupHeader
                  label={g.key}
                  count={g.items.length}
                  collapsed={collapsedGroups.has(g.key)}
                  onToggle={() => toggleGroup(g.key)}
                />
              )}
              {!collapsedGroups.has(g.key) && (
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))",
                  gap: 12, padding: 16,
                }}>
                  {g.items.map((r) => (
                    <ResourceCard key={r.id} resource={r} onDelete={handleDelete} />
                  ))}
                </div>
              )}
            </div>
          ))
        ) : (
          groups.map((g) => (
            <div key={g.key}>
              {groupBy !== "flat" && (
                <GroupHeader
                  label={g.key}
                  count={g.items.length}
                  collapsed={collapsedGroups.has(g.key)}
                  onToggle={() => toggleGroup(g.key)}
                />
              )}
              {!collapsedGroups.has(g.key) && g.items.map((r) => (
                <ResourceRow key={r.id} resource={r} onDelete={handleDelete} />
              ))}
            </div>
          ))
        )}
      </div>

      {/* ── FOOTER ── */}
      {filtered.length > 0 && (
        <footer style={{
          padding: "10px 18px",
          background: colors.gray50,
          borderTop: `1px solid ${colors.border}`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 11.5, color: colors.gray500,
        }}>
          <span>
            Showing <strong style={{ color: colors.gray800 }}>{filtered.length}</strong> of {resources.length} resources
          </span>
        </footer>
      )}
    </section>
  );
}

// Outer card wrapper style
const cardStyle = {
  background: colors.white,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  boxShadow: shadows.light,
  overflow: "hidden",
};
