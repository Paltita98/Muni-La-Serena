(() => {
    const dialog = document.getElementById('app-form-dialog');
    const frame = document.getElementById('app-form-frame');
    const title = document.getElementById('app-form-title');
    const closeButton = document.getElementById('app-form-close');

    if (!dialog || !frame || !title || !closeButton) return;

    const formPathPattern = /\/(?:nuevo|nueva|editar|registrar|actualizar|validar)(?:-|\/)|\/(?:actividades|evidencias)\/\d+\/?$|\/delegado\/compromisos\/\d+\/?$/i;
    let sourcePath = '';
    let hasLoadedForm = false;

    const closeDialog = (refresh = false) => {
        if (dialog.open) dialog.close();
        frame.src = 'about:blank';
        hasLoadedForm = false;
        if (refresh) window.location.reload();
    };

    document.addEventListener('click', (event) => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target === '_blank' || link.hasAttribute('download')) return;

        let destination;
        try {
            destination = new URL(link.href, window.location.href);
        } catch {
            return;
        }
        if (destination.origin !== window.location.origin || !formPathPattern.test(destination.pathname)) return;

        event.preventDefault();
        sourcePath = destination.pathname;
        hasLoadedForm = false;
        title.textContent = link.dataset.modalTitle || link.textContent.trim() || 'Formulario';
        frame.title = title.textContent;
        frame.src = destination.href;
        dialog.showModal();
        closeButton.focus();
    });

    frame.addEventListener('load', () => {
        if (!hasLoadedForm) {
            hasLoadedForm = true;
            return;
        }
        try {
            const currentPath = frame.contentWindow.location.pathname;
            if (currentPath !== sourcePath) closeDialog(true);
        } catch {
            closeDialog();
        }
    });

    closeButton.addEventListener('click', () => closeDialog());
    dialog.addEventListener('click', (event) => {
        if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        closeDialog();
    });
})();
