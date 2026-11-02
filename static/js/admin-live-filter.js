document.querySelectorAll('[data-live-filter]').forEach((section) => {
    const searchInput = section.querySelector('[data-search-input]');
    const filterInputs = [...section.querySelectorAll('[data-filter-key]')];
    const rows = [...section.querySelectorAll('[data-filter-row]')];
    const noResults = section.querySelector('[data-no-results]');
    const count = section.querySelector('[data-result-count]');

    const normalize = (value) => value
        .toLocaleLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();

    const applyFilters = () => {
        const query = normalize(searchInput?.value || '');
        let visibleCount = 0;

        rows.forEach((row) => {
            const matchesSearch = normalize(row.dataset.search || '').includes(query);
            const matchesFilters = filterInputs.every((input) => {
                const selected = normalize(input.value);
                if (!selected) return true;
                const values = normalize(row.dataset[input.dataset.filterKey] || '').split('|');
                return values.includes(selected);
            });
            const visible = matchesSearch && matchesFilters;
            row.hidden = !visible;
            if (visible) visibleCount += 1;
        });

        if (count) count.textContent = visibleCount;
        if (noResults) noResults.hidden = visibleCount > 0 || rows.length === 0;
    };

    searchInput?.addEventListener('input', applyFilters);
    filterInputs.forEach((input) => input.addEventListener('change', applyFilters));
    section.querySelector('[data-clear-filters]')?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        filterInputs.forEach((input) => { input.value = ''; });
        applyFilters();
    });
    applyFilters();
});
