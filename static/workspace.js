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

// Bounded, same-origin GETs read saved status. Never replay a form/provider call.
(() => {
  const watch = document.querySelector('[data-research-watch]');
  if (!watch) return;
  const endpoint = new URL(watch.dataset.researchWatch, window.location.origin);
  if (endpoint.origin !== window.location.origin) return;
  const message = watch.querySelector('[data-research-poll-status]');
  const started = Date.now();
  let count = 0;
  let failures = 0;
  let stopped = false;
  let timer;
  const pause = (text) => {
    stopped = true;
    if (message) message.textContent = text;
  };
  const check = async () => {
    if (stopped) return;
    if (++count > 40 || Date.now() - started > 6 * 60 * 1000) {
      pause('Automatic checks are paused. Use the status button to check again; your saved job is unchanged.');
      return;
    }
    if (!document.hidden && navigator.onLine !== false) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(endpoint.href, {
          method: 'GET', credentials: 'same-origin', cache: 'no-store',
          headers: {Accept: 'application/json'}, redirect: 'error', signal: controller.signal,
        });
        if ([401, 403, 404].includes(response.status)) {
          pause('This status is no longer accessible. Sign in again or return to your research.');
          return;
        }
        if (!response.ok) throw new Error('Status unavailable');
        const data = await response.json();
        if (typeof data.revision !== 'string' || !/^[a-f0-9]{64}$/.test(data.revision)) throw new Error('Invalid status');
        failures = 0;
        if (data.revision !== watch.dataset.researchRevision) {
          stopped = true;
          window.location.replace(window.location.href); // Existing server route authorizes report navigation.
          return;
        }
        if (data.terminal === true) {
          pause('Processing has stopped. Use the status button to review the saved result.');
          return;
        }
        if (message && Date.now() - started > 30000) {
          message.textContent = 'Still waiting for saved progress. A running worker is required; checking this page does not start another job.';
        }
      } catch (_) {
        if (++failures >= 3) {
          pause('Automatic checks could not reach Ayo. Use the status button when your connection returns.');
          return;
        }
      } finally {
        clearTimeout(timeout);
      }
    }
    timer = setTimeout(check, Math.min(4000 + count * 250, 12000));
  };
  timer = setTimeout(check, 4000);
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); }, {once: true});
  window.addEventListener('pageshow', (event) => { if (event.persisted) window.location.reload(); });
})();
