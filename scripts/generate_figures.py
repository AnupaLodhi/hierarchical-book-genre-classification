import json
from pathlib import Path
import matplotlib.pyplot as plt

EVALUATION = Path("results/evaluation")
FINAL = Path("results/final")
FIG = Path("results/figures")
FIG.mkdir(exist_ok=True)

evaluation = json.loads(
    (EVALUATION / "evaluation_summary.json").read_text(encoding="utf-8")
)

final = json.loads(
    (FINAL / "final_output.json").read_text(encoding="utf-8")
)

manual = json.loads(
    (FINAL / "manual_review.json").read_text(encoding="utf-8")
)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------
# Figure 1 — Original model availability
# --------------------------------------------------

availability = evaluation["availability"]

labels = ["0 models", "1 model", "2 models", "3 models"]
values = [int(availability.get(str(i), 0)) for i in range(4)]

fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(labels, values)

ax.set_title("Availability of Original LLM Annotations")
ax.set_ylabel("Number of Books")
ax.set_xlabel("Successful Original Annotators")

for bar, value in zip(bars, values):
    ax.text(
        bar.get_x() + bar.get_width()/2,
        value + 3,
        str(value),
        ha="center"
    )

save(fig, "fig1_model_availability")


# --------------------------------------------------
# Figure 2 — Three-model exact agreement
# --------------------------------------------------

n = evaluation["three_model_books"]

agreement_values = [
    evaluation["three_model_exact_genre"] / n * 100,
    evaluation["three_model_exact_metadata"] / n * 100,
    evaluation["three_model_exact_both"] / n * 100,
]

labels = ["Genre", "Metadata", "Combined"]

fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(labels, agreement_values)

ax.set_title(
    f"Exact Agreement Among Three Original LLMs (n={n})"
)
ax.set_ylabel("Exact Agreement (%)")
ax.set_ylim(0, 100)

for bar, value in zip(bars, agreement_values):
    ax.text(
        bar.get_x() + bar.get_width()/2,
        value + 2,
        f"{value:.2f}%",
        ha="center"
    )

save(fig, "fig2_three_model_agreement")


# --------------------------------------------------
# Figure 3 — Pairwise Jaccard similarity
# --------------------------------------------------

pairwise = evaluation["pairwise"]

pair_labels = [
    "Llama–Qwen",
    "Llama–Mistral",
    "Qwen–Mistral",
]

keys = [
    "llama_vs_qwen",
    "llama_vs_mistral",
    "qwen_vs_mistral",
]

genre = [
    pairwise[k]["mean_genre_jaccard"]
    for k in keys
]

metadata = [
    pairwise[k]["mean_metadata_jaccard"]
    for k in keys
]

x = range(len(keys))
width = 0.36

fig, ax = plt.subplots(figsize=(8, 5))

ax.bar(
    [i - width/2 for i in x],
    genre,
    width,
    label="Genre"
)

ax.bar(
    [i + width/2 for i in x],
    metadata,
    width,
    label="Metadata"
)

ax.set_xticks(list(x))
ax.set_xticklabels(pair_labels)
ax.set_ylabel("Mean Jaccard Similarity")
ax.set_ylim(0, 1)
ax.set_title("Pairwise Annotation Similarity")
ax.legend()

save(fig, "fig3_pairwise_jaccard")


# --------------------------------------------------
# Figure 4 — Final resolution outcomes
# --------------------------------------------------

methods = {}

for row in final:
    method = row["resolution_method"]
    methods[method] = methods.get(method, 0) + 1

resolution_labels = [
    "Perfect 3/3",
    "Majority 2/3",
    "Agreement 2/2",
    "Debate Resolver",
    "Manual Review",
]

resolution_values = [
    methods.get("perfect_3_of_3_consensus", 0),
    methods.get("agreement_2_of_3", 0),
    methods.get("agreement_2_of_2", 0),
    methods.get("debate_resolver_nex", 0),
    len(manual),
]

fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.bar(resolution_labels, resolution_values)

ax.set_title("Final Resolution Status Across 400 Books")
ax.set_ylabel("Number of Books")
ax.tick_params(axis="x", rotation=20)

for bar, value in zip(bars, resolution_values):
    ax.text(
        bar.get_x() + bar.get_width()/2,
        value + 3,
        str(value),
        ha="center"
    )

save(fig, "fig4_final_resolution")


# --------------------------------------------------
# Figure 5 — Manual review reasons
# --------------------------------------------------

reasons = {}

for row in manual:
    reason = row["review_reason"]
    reasons[reason] = reasons.get(reason, 0) + 1

reason_order = [
    "insufficient_original_annotations",
    "debate_api_error",
    "resolver_returned_empty",
    "no_filtered_tags",
]

reason_labels = [
    "Insufficient Original\nAnnotations",
    "Debate API\nQuota Error",
    "Resolver Returned\nEmpty",
    "No Filtered\nEvidence",
]

reason_values = [
    reasons.get(k, 0)
    for k in reason_order
]

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(reason_labels, reason_values)

ax.set_title("Reasons for Manual Review")
ax.set_ylabel("Number of Books")

for bar, value in zip(bars, reason_values):
    ax.text(
        bar.get_x() + bar.get_width()/2,
        value + 2,
        str(value),
        ha="center"
    )

save(fig, "fig5_manual_review_reasons")


print("\n===== FIGURES GENERATED =====")

for p in sorted(FIG.iterdir()):
    print(p)

print("\nPNG figures: 5")
print("PDF figures: 5")
print("✅ FIGURE GENERATION PASSED")
