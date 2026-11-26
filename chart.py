from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROWS = (
    ("positive", "Позитивные", "#3D9A62"),
    ("neutral", "Нейтральные", "#C4A35A"),
    ("negative", "Негативные", "#C45C4A"),
)


def render_chart(counts, total):
    """Рисует доли трёх классов и возвращает PNG."""
    labels = []
    percents = []
    colors = []
    annotations = []
    for key, title, color in _ROWS:
        count = counts.get(key, 0)
        percent = (100 * count / total) if total else 0
        labels.append(title)
        percents.append(percent)
        colors.append(color)
        annotations.append(f"{percent:.0f}% · {count}")

    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=140)
    fig.patch.set_facecolor("#f7f4ef")
    ax.set_facecolor("#f7f4ef")
    bars = ax.barh(labels, percents, color=colors, height=0.62)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Доля, %")
    ax.set_title(f"Тональность комментариев · всего {total}")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.invert_yaxis()
    for bar, note in zip(bars, annotations):
        ax.text(
            min(bar.get_width() + 1.5, 86),
            bar.get_y() + bar.get_height() / 2,
            note,
            va="center",
            fontsize=11,
        )
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    return buffer.getvalue()
