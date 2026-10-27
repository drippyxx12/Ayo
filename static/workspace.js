// Native forms retain server validation and normal browser navigation.
document.addEventListener('submit', (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.classList.contains('workspace-form')) return;
  form.setAttribute('aria-busy', 'true');
  const button = event.submitter;
  if (button && !button.dataset.originalLabel) {
    button.dataset.originalLabel = button.textContent;
    button.textContent = 'Working…';
    button.setAttribute('aria-disabled', 'true');
  }
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[aria-busy]').forEach((form) => form.removeAttribute('aria-busy'));
  document.querySelectorAll('[data-original-label]').forEach((button) => {
    button.textContent = button.dataset.originalLabel;
    button.removeAttribute('aria-disabled');
    delete button.dataset.originalLabel;
  });
});
