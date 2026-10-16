document.addEventListener("DOMContentLoaded", () => {
  const kind = document.getElementById("type");
  const category = document.getElementById("category_id");
  const reason = document.getElementById("reason_id");
  if (!kind || !category || !reason) return;
  const update = async () => {
    reason.replaceChildren(new Option("Select reason", ""));
    if (!category.value) return;
    try {
      const response = await fetch(`/transactions/api/reasons?category_id=${encodeURIComponent(category.value)}&type=${encodeURIComponent(kind.value)}`, {headers: {"Accept": "application/json"}});
      if (!response.ok) throw new Error(`Reason request failed (${response.status})`);
      const data = await response.json();
      for (const item of data.reasons) reason.add(new Option(item.name, item.id));
    } catch (error) {
      console.error(error);
      const option = new Option("Unable to load reasons; please retry", "");
      reason.replaceChildren(option);
    }
  };
  kind.addEventListener("change", () => {
    const selected = category.options[category.selectedIndex]?.text;
    const available = [...category.options].slice(1);
    for (const option of available) option.remove();
    fetch(`/admin/categories/api/categories?type=${encodeURIComponent(kind.value)}`, {headers: {"Accept": "application/json"}})
      .then(response => {if (!response.ok) throw new Error(`Category request failed (${response.status})`); return response.json();})
      .then(data => {for (const item of data.categories) category.add(new Option(item.name, item.id, false, item.name === selected)); update();})
      .catch(error => {console.error(error);});
  });
  category.addEventListener("change", update);
});
