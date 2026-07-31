#!/usr/bin/env python3
"""Render the two mandatory architecture diagrams as PNGs.

    python architecture/make_diagrams.py

Produces, at 300 DPI for print:
    architecture/AWS_Architecture.png       - how AWS services interact
    architecture/System_Architecture.png    - overall project workflow

The Mermaid sources in architecture/README.md remain the master reference;
these PNGs are the print artifacts for the report.

Requires matplotlib.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parent

# AWS-style service category colours (indicative, not official icons)
C_STORAGE = "#3F8624"   # green   - S3
C_COMPUTE = "#ED7100"   # orange  - Lambda
C_DB      = "#2E73B8"   # blue    - DynamoDB
C_NET     = "#8C4FFF"   # purple  - API Gateway, CloudFront
C_SEC     = "#DD344C"   # red     - IAM, Cognito
C_MGMT    = "#E7157B"   # magenta - CloudWatch, SNS, Budgets
C_OFF     = "#5A6570"   # grey    - offline / non-AWS
C_USER    = "#232F3E"   # navy    - actors

FONT = "DejaVu Sans"
GREY = "#4A5560"


def box(ax, x, y, w, h, title, sub="", colour="#333333", fs=8.5, sub_fs=7.0):
    """Rounded box with a coloured header bar. Returns (x, y, w, h)."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.3,rounding_size=0.8",
        linewidth=1.4, edgecolor=colour, facecolor="white", zorder=3))
    ax.add_patch(Rectangle((x + 0.12, y + h - 0.72), w - 0.24, 0.6,
                           facecolor=colour, edgecolor="none", zorder=4))
    ax.text(x + w / 2, y + h - 0.42, title, ha="center", va="center",
            fontsize=fs, color="white", fontweight="bold",
            family=FONT, zorder=5)
    if sub:
        ax.text(x + w / 2, y + (h - 0.72) / 2, sub, ha="center", va="center",
                fontsize=sub_fs, color="#20262E", family=FONT,
                zorder=5, linespacing=1.5)
    return (x, y, w, h)


def group(ax, x, y, w, h, label, colour="#8896A4"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.5",
        linewidth=1.1, edgecolor=colour, facecolor=colour,
        alpha=0.055, linestyle=(0, (5, 3)), zorder=1))
    ax.text(x + 0.6, y + h - 0.5, label, ha="left", va="center",
            fontsize=7.8, color=colour, fontweight="bold",
            family=FONT, zorder=2)


def arrow(ax, p1, p2, label="", colour=GREY, rad=0.0, fs=6.6, lw=1.3,
          offset=(0, 0), dashed=False):
    """Straight (or gently curved) arrow with an optional mid-point label."""
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=11,
        linewidth=lw, color=colour, zorder=6,
        linestyle="--" if dashed else "-",
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=2, shrinkB=3))
    if label:
        ax.text((p1[0] + p2[0]) / 2 + offset[0],
                (p1[1] + p2[1]) / 2 + offset[1],
                label, ha="center", va="center", fontsize=fs,
                color=colour, family=FONT, zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="none", alpha=0.92))


def elbow(ax, pts, label="", colour=GREY, fs=6.6, lw=1.3,
          dashed=False, label_pt=None, label_off=(0, 0)):
    """Right-angled polyline arrow through waypoints, head on the last segment.

    Used to route around boxes instead of sweeping across them.
    """
    ls = "--" if dashed else "-"
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs[:-1], ys[:-1], color=colour, linewidth=lw, linestyle=ls,
            zorder=6, solid_capstyle="round")
    ax.annotate("", xy=pts[-1], xytext=pts[-2],
                arrowprops=dict(arrowstyle="-|>", color=colour, linewidth=lw,
                                linestyle=ls, shrinkA=0, shrinkB=3,
                                mutation_scale=11), zorder=6)
    if label:
        if label_pt is None:
            mid = len(pts) // 2
            label_pt = ((pts[mid - 1][0] + pts[mid][0]) / 2,
                        (pts[mid - 1][1] + pts[mid][1]) / 2)
        ax.text(label_pt[0] + label_off[0], label_pt[1] + label_off[1], label,
                ha="center", va="center", fontsize=fs, color=colour,
                family=FONT, zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="none", alpha=0.94))


def canvas(w_in, h_in, xlim, ylim, title, subtitle):
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    ax.text(xlim[0] + 1.0, ylim[1] - 1.0, title, ha="left", va="top",
            fontsize=15, fontweight="bold", color=C_USER, family=FONT)
    ax.text(xlim[0] + 1.0, ylim[1] - 3.0, subtitle, ha="left", va="top",
            fontsize=8.6, color="#5A6570", family=FONT)
    return fig, ax


# ======================================================================
# DIAGRAM 1 - AWS Cloud Architecture
# ======================================================================
def aws_architecture():
    fig, ax = canvas(
        16, 12, (0, 100), (0, 82),
        "AWS Cloud Architecture",
        "Smart Storage Tier Recommender for Medical Image Repositories   |   "
        "BCSE355L Project Phase-I   |   Region: us-east-1")

    group(ax, 3, 50.0, 72, 14.5, "PRESENTATION  &  AUTHENTICATION")
    group(ax, 3, 35.0, 72, 13.5, "APPLICATION   (REST API)")
    group(ax, 3, 17.0, 72, 16.5, "PROCESSING  &  INTELLIGENCE")
    group(ax, 3, 3.0,  72, 12.5, "STORAGE   (S3 classes, transitions driven by Lifecycle)")
    group(ax, 78, 3.0, 20, 61.5, "SECURITY,  MONITORING  &  NOTIFICATIONS", C_SEC)

    # --- actors -------------------------------------------------------
    box(ax, 4, 69, 26, 5.8, "USERS",
        "Radiologist   |   Archive Admin   |   Reviewer", C_USER, 9)
    box(ax, 46, 69, 29, 5.8, "SCAN SOURCE",
        "PACS / DICOM uploader", C_USER, 9)

    # --- presentation + authentication --------------------------------
    box(ax, 5,  51.5, 20, 10.5, "Amazon Cognito",
        "User pool\nSign-in, JWT tokens\nRole-based access", C_SEC)
    box(ax, 28, 51.5, 21, 10.5, "Amazon CloudFront",
        "CDN edge delivery\nof the dashboard", C_NET)
    box(ax, 52, 51.5, 21, 10.5, "Amazon S3",
        "Static website hosting\nDashboard (HTML / JS)", C_STORAGE)

    # --- application ---------------------------------------------------
    box(ax, 5,  36.5, 20, 10, "Amazon API Gateway",
        "REST endpoints\nCognito authorizer", C_NET)
    box(ax, 28, 36.5, 21, 10, "AWS Lambda",
        "api_handler\nscans, costs, decisions", C_COMPUTE)
    box(ax, 52, 36.5, 21, 10, "Amazon DynamoDB",
        "ScanFeatures table\nmetadata, embedding,\ndecision + reason", C_DB)

    # --- processing -----------------------------------------------------
    box(ax, 5,  18.5, 20, 13, "Amazon S3",
        "medical-image-store\n\nScans land here\nin S3 Standard", C_STORAGE)
    box(ax, 28, 18.5, 21, 13, "AWS Lambda",
        "tier_inference\n\nStage 1  learned\nP(retrieved again)\n\n"
        "Stage 2  cost rule\nargmin expected cost", C_COMPUTE)
    box(ax, 52, 18.5, 21, 13, "S3 Lifecycle Rules",
        "Tag-filtered transitions\n\nThe model decides,\nAWS enforces", C_STORAGE)

    # --- storage classes -------------------------------------------------
    box(ax, 5.0,  4.5, 15.5, 8, "S3 Standard",
        "$0.023 /GB-mo\nmilliseconds", C_STORAGE, 8, 6.8)
    box(ax, 22.5, 4.5, 15.5, 8, "S3 Standard-IA",
        "~$0.0125 /GB-mo\nmin 30 days", C_STORAGE, 8, 6.8)
    box(ax, 40.0, 4.5, 15.5, 8, "Glacier Flexible",
        "$0.0036 /GB-mo\nmin 90 days", C_STORAGE, 8, 6.8)
    box(ax, 57.5, 4.5, 15.5, 8, "Glacier Deep Archive",
        "$0.00099 /GB-mo\nmin 180 d, up to 12 h", C_STORAGE, 8, 6.8)

    # --- security / monitoring / notifications column ---------------------
    box(ax, 79.5, 51.5, 17, 10.5, "AWS IAM",
        "Least-privilege\nexecution roles\nfor every service", C_SEC)
    box(ax, 79.5, 36.5, 17, 10, "Amazon CloudWatch",
        "Logs, metrics, alarms\n\ntier distribution,\nwrongly-archived rate", C_MGMT, 8.5, 6.6)
    box(ax, 79.5, 21.0, 17, 10.5, "Amazon SNS",
        "Notifications\n\n- restore complete\n- scan wrongly archived\n"
        "- inference failure", C_MGMT, 8.5, 6.6)
    box(ax, 79.5, 12.0, 17, 7, "Subscribers",
        "Email  /  SMS\nto archive admin", C_MGMT, 8.5, 6.8)
    box(ax, 79.5, 4.0, 17, 6, "AWS Budgets",
        "Spend alarm at $1", C_MGMT, 8.5, 6.8)

    # --- flows -----------------------------------------------------------
    arrow(ax, (15, 69), (15, 62.2), "sign in")
    arrow(ax, (27, 69.4), (38, 62.2), "HTTPS", rad=-0.08, offset=(2.5, 0.6))
    arrow(ax, (49, 56.7), (52, 56.7), "origin")
    arrow(ax, (12, 51.5), (12, 46.6), "JWT")
    elbow(ax, [(62, 51.5), (62, 49.4), (19, 49.4), (19, 46.6)],
          "dashboard calls the API", label_pt=(40, 49.4), label_off=(0, 0))
    arrow(ax, (25, 41.5), (28, 41.5), "route")
    arrow(ax, (49, 41.5), (52, 41.5), "query")

    # ingest routed around the outside left, avoiding the app layers
    elbow(ax, [(60, 69), (60, 67.0), (1.8, 67.0), (1.8, 25), (5, 25)],
          "PUT scan", label_pt=(1.8, 46), label_off=(0, 0))

    arrow(ax, (25, 25), (28, 25), "ObjectCreated\nevent", offset=(0, 2.6))
    arrow(ax, (45, 31.5), (58, 36.5), "features in\ndecision out", offset=(-4.5, 1.2))
    arrow(ax, (49, 22), (52, 22), "object tag")
    arrow(ax, (62, 18.5), (62, 12.7), "transition")
    arrow(ax, (13, 18.5), (13, 12.7), "")
    for a, b in ((20.5, 22.5), (38, 40), (55.5, 57.5)):
        arrow(ax, (a, 8.5), (b, 8.5), "")

    # monitoring + notifications, routed through the band gap
    elbow(ax, [(38.5, 31.5), (38.5, 34.2), (88, 34.2), (88, 36.5)],
          "metrics + logs", colour=C_MGMT, dashed=True,
          label_pt=(66, 34.2))
    arrow(ax, (88, 36.5), (88, 31.5), "alarm", colour=C_MGMT, offset=(-3.6, 0))
    arrow(ax, (88, 21.0), (88, 19.0), "publish", colour=C_MGMT, offset=(-4.2, 0))
    elbow(ax, [(96.5, 7.0), (99, 7.0), (99, 26.2), (96.5, 26.2)],
          "threshold\nbreached", colour=C_MGMT, dashed=True,
          label_pt=(99, 16.5), label_off=(0, 0), fs=6.0)

    ax.text(50, 1.0,
            "Serverless throughout - no EC2, no RDS - so idle cost is zero.   "
            "Lambda, DynamoDB, Cognito, SNS, CloudWatch and CloudFront all sit "
            "inside always-free AWS allowances.\n"
            "AWS IAM governs every service shown; individual role bindings are "
            "omitted from the diagram for readability.",
            ha="center", va="bottom", fontsize=7.3, color="#5A6570",
            style="italic", family=FONT, linespacing=1.6)

    fig.tight_layout(pad=0.4)
    p = OUT / "AWS_Architecture.png"
    fig.savefig(p, dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return p


# ======================================================================
# DIAGRAM 2 - Complete System Architecture
# ======================================================================
def system_architecture():
    fig, ax = canvas(
        16, 11.5, (0, 100), (0, 76),
        "Complete System Architecture",
        "End-to-end workflow: offline training, online tier decision, "
        "feedback loop and cost evaluation")

    group(ax, 3, 55.5, 94, 15.0,
          "1.   OFFLINE   -   runs once, on a laptop or Google Colab, zero cost")
    group(ax, 3, 33.0, 94, 20.5, "2.   ONLINE   -   per-scan decision on AWS")
    group(ax, 3, 18.0, 94, 13.0,
          "3.   FEEDBACK   -   retrieval events refine future decisions")
    group(ax, 3, 1.5, 94, 14.5,
          "4.   EVALUATION   -   offline cost projection over all 112,120 records")

    # --- offline band ---------------------------------------------------
    box(ax, 5,  57, 16, 11, "Dataset",
        "NIH ChestX-ray14\n112,120 images\n30,805 patients\nfully open", C_OFF)
    box(ax, 23, 57, 16, 11, "preprocessing.py",
        "Parse metadata\nDerive label from\nFollow-up #\nSplit by Patient ID", C_OFF)
    box(ax, 41, 57, 16, 11, "Embedding extractor",
        "MobileNetV3\n128-dim vector\nper image\n(free Colab GPU)", C_OFF)
    box(ax, 59, 57, 17, 11, "train.py",
        "Stage 1 model\nP(retrieved again)\ncalibrated, not just\naccurate", C_OFF)
    box(ax, 78, 57, 17, 11, "Artifacts",
        "model.pkl  ->  Lambda\nembeddings  ->  DynamoDB", C_OFF)

    # --- online band -----------------------------------------------------
    box(ax, 5,  35, 16, 16, "Scan ingest",
        "New scan arrives\n\nLands in\nS3 Standard\n\nS3 event fires", C_STORAGE)
    box(ax, 23, 35, 16, 16, "Feature assembly",
        "DICOM metadata\n+\nimage embedding\n+\naccess history\n\n"
        "read from DynamoDB", C_DB)
    box(ax, 41, 35, 16, 16, "STAGE 1  (learned)",
        "Gradient-boosted\nclassifier\n\nOutputs probability P\nthat the scan is\n"
        "retrieved again", C_COMPUTE)
    box(ax, 59, 35, 17, 16, "STAGE 2  (explicit rule)",
        "argmin expected cost\n\nstorage cost\n+ P x retrieval cost\n"
        "+ P x clinical penalty\n+ transition cost\n\n128 KB floor +\n40 KB overhead",
        C_COMPUTE)
    box(ax, 78, 35, 17, 16, "Decision applied",
        "S3 object tag\nwritten\n\nLifecycle rule\nperforms the\ntransition\n\n"
        "Reason logged\nto DynamoDB", C_STORAGE)

    # --- feedback band ----------------------------------------------------
    box(ax, 5,  19.5, 20, 10, "Retrieval request",
        "Doctor asks for a scan", C_USER, 8.5)
    box(ax, 27, 19.5, 20, 10, "Fast tier hit",
        "Served in milliseconds\nAccess history updated", C_STORAGE, 8.5)
    box(ax, 49, 19.5, 22, 10, "Archive miss",
        "Restore job, hours of delay\nLogged as WRONGLY ARCHIVED\n"
        "SNS alert raised", C_SEC, 8.5)
    box(ax, 73, 19.5, 22, 10, "History updated",
        "DynamoDB access counters\nfeed the next decision", C_DB, 8.5)

    # --- evaluation band ---------------------------------------------------
    box(ax, 5,  3.0, 21, 11.5, "Cost model",
        "Full AWS price list\nstorage + requests\n+ transitions + retrieval\n"
        "+ minimum durations", C_MGMT, 8.5)
    box(ax, 28, 3.0, 15, 11.5, "Baseline 1",
        "All S3 Standard\n\nthe expensive\nstatus quo", C_OFF, 8.5, 6.8)
    box(ax, 45, 3.0, 15, 11.5, "Baseline 2",
        "Age-based rule\n\nwhat hospitals\ndo today", C_OFF, 8.5, 6.8)
    box(ax, 62, 3.0, 15, 11.5, "Baseline 3",
        "S3 Intelligent-\nTiering\n\nAWS's own answer", C_OFF, 8.5, 6.8)
    box(ax, 79, 3.0, 16, 11.5, "Results",
        "Monthly bill\n+ wrongly-archived\nrate, reported\ntogether", C_MGMT, 8.5, 6.8)

    # --- flows --------------------------------------------------------------
    for a, b in ((21, 23), (39, 41), (57, 59), (76, 78)):
        arrow(ax, (a, 62.5), (b, 62.5))
    for a, b in ((21, 23), (39, 41), (57, 59), (76, 78)):
        arrow(ax, (a, 43), (b, 43))
    for a, b in ((25, 27), (47, 49), (71, 73)):
        arrow(ax, (a, 24.5), (b, 24.5))
    for a, b in ((26, 28), (43, 45), (60, 62), (77, 79)):
        arrow(ax, (a, 8.7), (b, 8.7))

    arrow(ax, (86, 56.6), (86, 51.3), "model + embeddings deployed",
          offset=(0, -0.2), fs=6.4)
    arrow(ax, (86, 34.6), (86, 29.9), "scan stored")
    arrow(ax, (15, 19.1), (15, 14.8), "observed behaviour")

    # feedback loop routed through the band gap, not across the boxes
    elbow(ax, [(95, 24.5), (98.4, 24.5), (98.4, 32.1), (31, 32.1), (31, 34.6)],
          "access history feeds the next decision",
          colour=C_DB, dashed=True, label_pt=(64, 32.1), fs=6.8)

    ax.text(50, 0.3,
            "Two-track evaluation:  the mechanism is proven live on ~1,000 images "
            "inside the AWS free allowance, while cost is projected across all "
            "112,120 records from AWS's published price list.",
            ha="center", va="bottom", fontsize=7.4, color="#5A6570",
            style="italic", family=FONT)

    fig.tight_layout(pad=0.4)
    p = OUT / "System_Architecture.png"
    fig.savefig(p, dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return p


if __name__ == "__main__":
    for p in (aws_architecture(), system_architecture()):
        print(f"wrote {p.name}")
