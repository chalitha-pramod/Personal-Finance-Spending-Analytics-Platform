document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("community-filters");
  if (!form) return;

  const periodField = document.getElementById("community-period");
  const startField = document.getElementById("community-start");
  const endField = document.getElementById("community-end");
  const loading = document.getElementById("community-loading");
  const error = document.getElementById("community-error");
  const chartInstances = new Map();
  let activeRequest;
  const colors = {
    navy: "#14213d",
    teal: "#0d9488",
    green: "#16a34a",
    amber: "#d97706",
    red: "#dc2626",
    slate: "#64748b"
  };

  const showEmpty = (canvasId, emptyId, available, message) => {
    const canvas = document.getElementById(canvasId);
    const empty = document.getElementById(emptyId);
    if (available) {
      empty.classList.add("d-none");
      canvas.closest(".chart-container").classList.remove("d-none");
      return true;
    }
    chartInstances.get(canvasId)?.destroy();
    chartInstances.delete(canvasId);
    canvas.closest(".chart-container").classList.add("d-none");
    empty.textContent = message || "Not enough community data to display this chart.";
    empty.classList.remove("d-none");
    return false;
  };

  const drawChart = (canvasId, config) => {
    const canvas = document.getElementById(canvasId);
    let chart = chartInstances.get(canvasId);
    if (chart && chart.config.type !== config.type) {
      chart.destroy();
      chart = null;
    }
    if (!chart) {
      chart = new Chart(canvas, config);
      chartInstances.set(canvasId, chart);
      return;
    }
    chart.data.labels = config.data.labels;
    chart.data.datasets = config.data.datasets;
    chart.options = config.options;
    chart.update();
  };

  const formatCurrency = currency => new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2
  });

  const drawCurrencyAxis = formatter => ({
    ticks: {callback: value => formatter.format(value)}
  });

  const render = (data, currency) => {
    const formatter = formatCurrency(currency);
    document.getElementById("community-eligibility").textContent = data.eligibility;
    const overviewMessage = document.getElementById("overview-message");
    const ratioNote = document.getElementById("community-ratio-note");
    if (data.overview.available) {
      document.getElementById("community-income").textContent = formatter.format(data.overview.income);
      document.getElementById("community-expenses").textContent = formatter.format(data.overview.expenses);
      document.getElementById("community-difference").textContent = formatter.format(data.overview.difference);
      document.getElementById("community-ratio").textContent = data.overview.spending_ratio === null
        ? "N/A"
        : `${data.overview.spending_ratio.toFixed(1)}%`;
      ratioNote.textContent = data.overview.spending_ratio === null
        ? "Not meaningful when recorded income is zero"
        : "Recorded expenses as a share of recorded income";
      overviewMessage.textContent = data.overview.message || "";
    } else {
      for (const id of ["community-income", "community-expenses", "community-difference", "community-ratio"]) {
        document.getElementById(id).textContent = "—";
      }
      overviewMessage.textContent = data.overview.message;
      ratioNote.textContent = "Not enough data to calculate safely";
    }

    if (showEmpty("community-category-chart", "community-category-empty", data.categories.available, data.categories.message)) {
      const items = data.categories.items;
      drawChart("community-category-chart", {
        type: "doughnut",
        data: {
          labels: items.map(item => item.name),
          datasets: [{
            data: items.map(item => item.amount),
            backgroundColor: [colors.navy, colors.teal, colors.green, colors.amber, colors.red, colors.slate]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {position: "bottom"},
            tooltip: {
              callbacks: {
                label: item => {
                  const category = items[item.dataIndex];
                  return `${category.name}: ${formatter.format(category.amount)} (${category.percentage.toFixed(1)}%)`;
                }
              }
            }
          }
        }
      });
    }

    const age = data.age_groups;
    const ageLabels = age.items.map(item => item.label);
    document.getElementById("age-suppression-note").textContent = age.has_suppressed_groups
      ? "Some age groups are not shown because they do not meet the privacy threshold."
      : "Age groups with no recorded activity are not included.";
    if (showEmpty("community-age-chart", "community-age-empty", age.available, age.message)) {
      drawChart("community-age-chart", {
        type: "bar",
        data: {
          labels: ageLabels,
          datasets: [
            {label: "Average expenses per contributor", data: age.items.map(item => item.average_expenses), backgroundColor: colors.red},
            {label: "Average income per contributor", data: age.items.map(item => item.average_income), backgroundColor: colors.green}
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {y: {...drawCurrencyAxis(formatter), beginAtZero: true}},
          plugins: {tooltip: {callbacks: {label: item => `${item.dataset.label}: ${formatter.format(item.raw)}`}}}
        }
      });
      document.getElementById("age-spending-leaders").textContent =
        `Among groups meeting the privacy threshold, highest average spending: ${age.highest_spending}; lowest: ${age.lowest_spending}.`;
    } else {
      document.getElementById("age-spending-leaders").textContent = "";
    }

    if (showEmpty("community-income-age-chart", "community-income-age-empty", age.available, age.message)) {
      drawChart("community-income-age-chart", {
        type: "bar",
        data: {
          labels: ageLabels,
          datasets: [{
            label: "Average recorded income per contributor",
            data: age.items.map(item => item.average_income),
            backgroundColor: colors.green
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {y: {...drawCurrencyAxis(formatter), beginAtZero: true}},
          plugins: {legend: {display: false}, tooltip: {callbacks: {label: item => formatter.format(item.raw)}}}
        }
      });
      document.getElementById("age-income-leaders").textContent =
        `Among groups meeting the privacy threshold, highest average income: ${age.highest_income}; lowest: ${age.lowest_income}.`;
    } else {
      document.getElementById("age-income-leaders").textContent = "";
    }

    const trendDescription = document.getElementById("community-trend-description");
    trendDescription.textContent = data.trends.available
      ? `${data.period.interval === "yearly" ? "Yearly" : "Monthly"} totals for eligible contributors, ${data.period.start} to ${data.period.end}.`
      : "The full series is withheld when any reporting interval falls below the privacy threshold.";
    if (showEmpty("community-trend-chart", "community-trend-empty", data.trends.available, data.trends.message)) {
      drawChart("community-trend-chart", {
        type: "line",
        data: {
          labels: data.trends.points.map(point => point.period),
          datasets: [
            {label: "Recorded income", data: data.trends.points.map(point => point.income), borderColor: colors.green, backgroundColor: `${colors.green}22`, fill: true, tension: .25},
            {label: "Recorded expenses", data: data.trends.points.map(point => point.expenses), borderColor: colors.red, backgroundColor: `${colors.red}18`, fill: true, tension: .25}
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {mode: "index", intersect: false},
          scales: {y: {...drawCurrencyAxis(formatter), beginAtZero: true}}
        }
      });
    }

    if (showEmpty("community-person-chart", "community-person-empty", age.available, age.message)) {
      drawChart("community-person-chart", {
        type: "bar",
        data: {
          labels: ageLabels,
          datasets: [{
            label: "Average recorded expenses per contributor",
            data: age.items.map(item => item.average_expenses),
            backgroundColor: colors.teal
          }]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          scales: {x: {...drawCurrencyAxis(formatter), beginAtZero: true}},
          plugins: {legend: {display: false}, tooltip: {callbacks: {label: item => formatter.format(item.raw)}}}
        }
      });
    }

    if (showEmpty("community-category-trend-chart", "community-category-trend-empty", data.category_trends.available, data.category_trends.message)) {
      drawChart("community-category-trend-chart", {
        type: "bar",
        data: {
          labels: data.category_trends.labels,
          datasets: data.category_trends.datasets.map((dataset, index) => ({
            ...dataset,
            backgroundColor: [colors.navy, colors.teal, colors.green, colors.amber, colors.red, colors.slate][index % 6]
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {stacked: true},
            y: {...drawCurrencyAxis(formatter), stacked: true, beginAtZero: true}
          }
        }
      });
    }
  };

  const updateCustomDates = () => {
    const isCustom = periodField.value === "custom";
    document.querySelectorAll(".custom-community-date").forEach(field => {
      field.classList.toggle("d-none", !isCustom);
    });
    startField.required = isCustom;
    endField.required = isCustom;
  };

  const loadAnalytics = async () => {
    activeRequest?.abort();
    activeRequest = new AbortController();
    const request = activeRequest;
    const params = new URLSearchParams(new FormData(form));
    const currency = params.get("currency");
    loading.classList.remove("d-none");
    error.classList.add("d-none");
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const response = await fetch(`${form.dataset.endpoint}?${params}`, {
        headers: {"Accept": "application/json"},
        signal: request.signal
      });
      if (!response.ok) throw new Error(`Community analytics request failed (${response.status})`);
      const data = await response.json();
      if (activeRequest !== request) return;
      render(data, currency);
    } catch (errorValue) {
      if (errorValue.name !== "AbortError") {
        console.error(errorValue);
        error.classList.remove("d-none");
      }
    } finally {
      if (activeRequest === request) {
        loading.classList.add("d-none");
        form.querySelector('button[type="submit"]').disabled = false;
      }
    }
  };

  periodField.addEventListener("change", updateCustomDates);
  form.addEventListener("submit", event => {
    event.preventDefault();
    loadAnalytics();
  });
  updateCustomDates();
  loadAnalytics();
});
