import { useState } from "react";
import { Link } from "react-router-dom";

import { ScrollSurface } from "../components/ScrollSurface";
import { TemplateFillTree } from "../components/TemplateFillTree";
import { StatusChip } from "../components/StatusChip";
import { useTracker } from "../lib/tracker-context";
import { deriveTemplateWorkspaceModel } from "../lib/workspace-models";

type TemplateStudioSection = "overview" | "validation" | "coverage" | "tree";

export function TemplateStudioPage() {
  const { templateStudio } = useTracker();
  const model = deriveTemplateWorkspaceModel(templateStudio);
  const [activeSection, setActiveSection] = useState<TemplateStudioSection>("overview");

  return (
    <div className="page-grid">
      <section className="card card-pad workspace-header-card compact" style={{ gridColumn: "span 12" }}>
        <div className="workspace-header-copy">
          <div>
            <p className="workspace-header-description accent">
              Moradin Payload
            </p>
          </div>
          <div className="workspace-header-actions">
            <Link className="workspace-header-pill-link primary" to="/deploy/map">
              Open Deploy Map
            </Link>
            <Link className="workspace-header-pill-link" to="/deploy/builder">
              Open Builder
            </Link>
          </div>
        </div>
        <div className="workspace-header-chips">
          <StatusChip tone="info">{model.templateId}</StatusChip>
          <StatusChip tone="success">{model.templateVersion}</StatusChip>
          <StatusChip tone={model.validationStatus.tone}>{model.validationStatus.label}</StatusChip>
          <StatusChip tone={model.dryRunStatus.tone}>{model.dryRunStatus.label}</StatusChip>
        </div>
        <nav className="workspace-tabs" aria-label="Moradin payload navigation">
          {[
            { id: "overview", label: "Overview" },
            { id: "validation", label: "Validation" },
            { id: "coverage", label: "Coverage" },
            { id: "tree", label: "Payload Tree" },
          ].map((section) => (
            <button
              key={section.id}
              type="button"
              className={`workspace-tab ${activeSection === section.id ? "active" : ""}`.trim()}
              onClick={() => setActiveSection(section.id as TemplateStudioSection)}
            >
              {section.label}
            </button>
          ))}
        </nav>
      </section>

      {activeSection === "overview" ? (
        <>
          <section className="card card-pad" style={{ gridColumn: "span 3" }}>
            <p className="card-head">Sections</p>
            <p className="metric">{model.sectionCount}</p>
            <p className="metric-sub">Stable docs sections defined for the alpha payload cut.</p>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 3" }}>
            <p className="card-head">Placeholders</p>
            <p className="metric">{model.placeholderCount}</p>
            <p className="metric-sub">Payload sections still scaffolded for downstream hydration.</p>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 3" }}>
            <p className="card-head">Ready Sections</p>
            <p className="metric">{model.readyCount}</p>
            <p className="metric-sub">Sections with canonical content beyond placeholder scaffolding.</p>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 3" }}>
            <p className="card-head">Path Convention</p>
            <p className="metric" style={{ fontSize: "1.15rem" }}>{model.pathConvention}</p>
            <p className="metric-sub">{`Compatibility: ${model.compatibilityMode} · Stage: ${model.releaseStage}`}</p>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 6" }}>
            <p className="card-head">Validation And Smoke Tests</p>
            <div className="projects-detail-list" style={{ marginTop: "0.75rem" }}>
              <div>
                <strong>Validation</strong>
                <small>{model.validationStatus.label}</small>
              </div>
              <div>
                <strong>Dry-run deployment</strong>
                <small>{model.dryRunStatus.label}</small>
              </div>
              <div>
                <strong>Payload version</strong>
                <small>{model.templateVersion}</small>
              </div>
              <div>
                <strong>Manager harness version</strong>
                <small>{model.managerVersion}</small>
              </div>
            </div>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 6" }}>
            <p className="card-head">Inventory</p>
            <div className="projects-detail-list" style={{ marginTop: "0.75rem" }}>
              <div>
                <strong>Total files</strong>
                <small>{model.inventory.total_files}</small>
              </div>
              <div>
                <strong>Docs markdown</strong>
                <small>{model.inventory.docs_markdown_count}</small>
              </div>
              <div>
                <strong>Harness markdown</strong>
                <small>{model.inventory.harness_markdown_count}</small>
              </div>
              <div>
                <strong>Placeholder documents</strong>
                <small>{model.inventory.placeholder_count}</small>
              </div>
            </div>
          </section>
        </>
      ) : null}

      {activeSection === "validation" ? (
        <>
          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <p className="card-head">Validation And Smoke Tests</p>
            <div className="projects-detail-list" style={{ marginTop: "0.75rem" }}>
              <div>
                <strong>Validation</strong>
                <small>{model.validationStatus.label}</small>
              </div>
              <div>
                <strong>Dry-run deployment</strong>
                <small>{model.dryRunStatus.label}</small>
              </div>
              <div>
                <strong>Payload version</strong>
                <small>{model.templateVersion}</small>
              </div>
              <div>
                <strong>Manager harness version</strong>
                <small>{model.managerVersion}</small>
              </div>
            </div>
            {templateStudio?.validation.messages?.length ? (
              <div className="template-messages">
                {templateStudio.validation.messages.slice(0, 8).map((message) => (
                  <p key={message} className="metric-sub">
                    {message}
                  </p>
                ))}
              </div>
            ) : (
              <p className="metric-sub" style={{ marginTop: "0.85rem" }}>
                No validation messages were recorded for the current Moradin payload snapshot.
              </p>
            )}
          </section>
        </>
      ) : null}

      {activeSection === "coverage" ? (
        <section className="card card-pad" style={{ gridColumn: "span 12" }}>
          <p className="card-head">Section Coverage</p>
          <ScrollSurface className="effects-table-wrap" style={{ marginTop: "0.8rem" }}>
            <table className="table effects-table">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Questions</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {model.sections.map((section) => (
                  <tr key={section.section}>
                    <td>{section.section}</td>
                    <td>{section.title}</td>
                    <td>
                      <StatusChip tone={section.placeholder ? "warning" : "success"}>
                        {section.placeholder ? "Placeholder" : section.status || "Ready"}
                      </StatusChip>
                    </td>
                    <td>{section.owner || "ui_builder"}</td>
                    <td>{section.question_count}</td>
                    <td className="mono">{section.relative_path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollSurface>
        </section>
      ) : null}

      {activeSection === "tree" ? (
        <TemplateFillTree
          title="Payload Coverage"
          description="Baseline Moradin payload paths stay visible here so operators can inspect the downstream shape before running Builder or materializing into a target repository."
        />
      ) : null}
    </div>
  );
}
