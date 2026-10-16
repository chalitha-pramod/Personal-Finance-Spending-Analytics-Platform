document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("analytics-charts");
  const error = document.getElementById("analyticsError");
  if (!container) return;

  try {
    const response = await fetch(container.dataset.endpoint, {
      headers: {"Accept": "application/json"}
    });
    if (!response.ok) throw new Error(`Analytics request failed (${response.status})`);
    const data = await response.json();
    const money = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: data.currency
    });
    const drawAgeBandChart = (id, label, key, color) => {
      const canvas = document.getElementById(id);
      if (!canvas) return;
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.groups.map(row => row.band),
          datasets: [{
            label,
            data: data.groups.map(row => row[key]),
            backgroundColor: color
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {callback: value => money.format(value)}
            }
          }
        }
      });
    };

    drawAgeBandChart("incomeGroups", "Average income", "avg_income", "#16a34a");
    drawAgeBandChart("expenseGroups", "Average expenses", "avg_expense", "#dc2626");

    const categoryCanvas = document.getElementById("categoryTotals");
    if (categoryCanvas) {
      new Chart(categoryCanvas, {
        type: "bar",
        data: {
          labels: data.categories.map(row => row.name),
          datasets: [{
            label: "Total spending",
            data: data.categories.map(row => row.amount),
            backgroundColor: "#14213d"
          }]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          scales: {
            x: {ticks: {callback: value => money.format(value)}}
          }
        }
      });
    }

    const monthlyCanvas = document.getElementById("monthlyTrend");
    if (monthlyCanvas) {
      new Chart(monthlyCanvas, {
        type: "line",
        data: {
          labels: data.monthly.map(row => row.period),
          datasets: [
            {label: "Income", data: data.monthly.map(row => row.income), borderColor: "#16a34a"},
            {label: "Expenses", data: data.monthly.map(row => row.expense), borderColor: "#dc2626"}
          ]
        },
        options: {
          responsive: true,
          scales: {y: {ticks: {callback: value => money.format(value)}}}
        }
      });
    }

    const ageCategoryCanvas = document.getElementById("ageCategoryChart");
    if (ageCategoryCanvas) {
      const bands = [...new Set(data.age_categories.map(row => row.band))];
      const categories = [...new Set(data.age_categories.map(row => row.name))];
      const colors = ["#14213d", "#16a34a", "#d97706", "#0d9488", "#dc2626"];
      new Chart(ageCategoryCanvas, {
        type: "bar",
        data: {
          labels: bands,
          datasets: categories.map((name, index) => ({
            label: name,
            data: bands.map(band => data.age_categories.find(
              row => row.band === band && row.name === name
            )?.amount || 0),
            backgroundColor: colors[index % colors.length]
          }))
        },
        options: {
          responsive: true,
          scales: {
            x: {stacked: true},
            y: {
              stacked: true,
              beginAtZero: true,
              ticks: {callback: value => money.format(value)}
            }
          }
        }
      });
    }
  } catch (errorValue) {
    console.error(errorValue);
    if (error) error.classList.remove("d-none");
  }
});
