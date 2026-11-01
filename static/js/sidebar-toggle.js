(() => {
  const sidebars = document.querySelectorAll('.sidebar');
  const mobileViewport = window.matchMedia('(max-width: 760px)');

  sidebars.forEach((sidebar, index) => {
    if (sidebar.tagName !== 'ASIDE') return;

    const header = sidebar.firstElementChild;
    const navigation = sidebar.querySelector('nav');
    if (!header || !navigation) return;

    const navigationId = `sidebar-navigation-${index + 1}`;
    navigation.id = navigationId;

    const toggle = document.createElement('button');
    const icon = document.createElement('span');
    const label = document.createElement('span');

    toggle.type = 'button';
    toggle.className = 'sidebar-toggle';
    toggle.setAttribute('aria-controls', navigationId);
    icon.className = 'sidebar-toggle-icon';
    icon.setAttribute('aria-hidden', 'true');
    label.className = 'sidebar-toggle-label';
    toggle.append(icon, label);
    header.append(toggle);

    const setCollapsed = (isCollapsed) => {
      sidebar.classList.toggle('is-collapsed', isCollapsed);
      toggle.setAttribute('aria-expanded', String(!isCollapsed));
      toggle.setAttribute('aria-label', isCollapsed ? 'Mostrar menú' : 'Ocultar menú');
      icon.textContent = isCollapsed ? '☰' : '×';
      label.textContent = mobileViewport.matches
        ? (isCollapsed ? 'Menú' : 'Cerrar')
        : (isCollapsed ? 'Expandir' : 'Contraer');
    };

    setCollapsed(mobileViewport.matches);

    toggle.addEventListener('click', () => {
      setCollapsed(!sidebar.classList.contains('is-collapsed'));
    });

    navigation.addEventListener('click', (event) => {
      if (!event.target.closest('a') || !mobileViewport.matches) return;
      setCollapsed(true);
    });

    mobileViewport.addEventListener('change', (event) => {
      setCollapsed(event.matches);
    });
  });
})();