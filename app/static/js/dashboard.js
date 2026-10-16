document.addEventListener("DOMContentLoaded", async () => {
  const error = document.getElementById("chartError");
  try {
    const response = await fetch(`/api/chart-data${window.location.search}`, {headers: {"Accept": "application/json"}});
    if (!response.ok) throw new Error(`Chart request failed (${response.status})`);
    const data = await response.json();
    const formatter = new Intl.NumberFormat(undefined, {style: "currency", currency: data.currency});
    const trend = document.getElementById("trendChart");
    if (trend && data.labels.length) new Chart(trend, {type: "line", data: {labels: data.labels, datasets: [
      {label: "Income", data: data.income, borderColor: "#16a34a", backgroundColor: "#16a34a22", tension: .28},
      {label: "Expenses", data: data.expenses, borderColor: "#dc2626", backgroundColor: "#dc262622", tension: .28}
    ]}, options: {responsive: true, interaction: {mode: "index", intersect: false}, scales: {y: {ticks: {callback: value => formatter.format(value)}}}}});
    const category = document.getElementById("categoryChart");
    if (category && data.category_labels.length) new Chart(category, {type: "doughnut", data: {labels: data.category_labels, datasets: [{data: data.category_values, backgroundColor: ["#14213d","#16a34a","#d97706","#0d9488","#334155","#dc2626","#64748b"]}]}, options: {responsive: true, plugins: {legend: {position: "bottom"}, tooltip: {callbacks: {label: item => `${item.label}: ${formatter.format(item.raw)}`}}}}});
    const reasons = document.getElementById("reasonChart");
    if (reasons && data.reason_labels.length) new Chart(reasons, {type: "bar", data: {labels: data.reason_labels, datasets: [{label: "Expenses", data: data.reason_values, backgroundColor: "#d97706"}]}, options: {responsive: true, plugins: {legend: {display: false}}, indexAxis: "y", scales: {x: {ticks: {callback: value => formatter.format(value)}}}}});
  } catch (errorValue) {
    console.error(errorValue);
    if (error) error.classList.remove("d-none");
  }
});
