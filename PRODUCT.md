# CloudTierRecommender

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Archive administrators inspect storage placement and restore complete imaging studies. Researchers inspect permitted imaging and clinical context. Dataset operators validate imports and run pretrained MRI analysis. Faculty evaluate the course prototype and its evidence.

## Product Purpose

Cloud storage optimization for cancer imaging studies, supported by verified clinical linkage and pretrained multimodal MRI analysis. The project owner confirmed this direction on 11 October 2026 and authorized implementation of the v2 PRD and dashboard design.

## Capabilities and Truth

The v1 application provides a React/Vite frontend, Flask/SQLite local API, shared storage policy, and AWS infrastructure. V2 introduces study/series/object organization, clinical joins, complete MRI sequence sets, analysis provenance and study-aware placement. Dataset access, checkpoint execution and cloud deployment require their own evidence. Demonstration cohorts and simulated costs must remain labeled.

## Constraints

Storage optimization is the primary objective. Use published pretrained weights without local training. The selected MRI path is MONAI BraTS SegResNet; MRI results must not be presented as a retrieval forecast or diagnosis. Use permitted de-identified data and exact clinical joins. Preserve the v1 interfaces and unrelated existing changes. Keep raw image data and checkpoints out of Git.

## Brand Commitments

The owner approved the proposed archive dashboard direction and requested a coordinated colour design, clearer UI and animations. A light archive workspace, teal actions, navy navigation and dark MRI canvas are the design anchors. Motion should communicate navigation and operation progress, and respect reduced motion.

## Evidence and Specifications

Product target: architecture/PRD_V2_TCIA_BRATS.md. Dashboard brief: architecture/DASHBOARD_V2_SPEC.md. Existing implementation record: architecture/PRODUCT_AND_IMPLEMENTATION.md. Mark partially delivered requirements explicitly.
