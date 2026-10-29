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
  let dispatching = false;
  let attemptedDispatch = false;
  const dispatchForm = watch.querySelector('form[data-research-dispatch]');
  const dispatchJob = async () => {
    if (!dispatchForm || attemptedDispatch) return;
    const target = new URL(dispatchForm.action, window.location.origin);
    if (target.origin !== window.location.origin) return;
    attemptedDispatch = true;
    dispatching = true;
    const button = dispatchForm.querySelector('button[type=submit]');
    const note = dispatchForm.querySelector('[data-worker-dispatch-status]');
    if (button) { button.disabled = true; button.textContent = 'Research is running…'; }
    if (note) note.textContent = 'The worker is checking permitted evidence. Keep this page open for the result.';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 110000);
    try {
      const response = await fetch(target.href, {method: 'POST', body: new FormData(dispatchForm),
        credentials: 'same-origin', headers: {Accept: 'application/json'},
        redirect: 'error', signal: controller.signal});
      if (!response.ok) throw new Error('Worker command unavailable');
      const result = await response.json();
      if (typeof result.processed !== 'boolean') throw new Error('Invalid worker response');
      if (!result.processed) {
        if (button) button.textContent = 'Checking saved status…';
        if (note) note.textContent = 'This command did not start another attempt. Ayo is checking the saved job status.';
        return; // A busy/finished job must not reload into another automatic POST.
      }
      stopped = true;
      window.location.replace(window.location.href);
    } catch (_) {
      // An interrupted response may have performed work. Never resubmit it here.
      if (note) note.textContent = 'The worker response was interrupted or unavailable. Check saved status; Ayo has not automatically sent another request.';
      if (button) button.textContent = 'Check the saved research status';
    } finally {
      dispatching = false;
      clearTimeout(timeout);
    }
  };
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
          if (dispatching) {
            watch.dataset.researchRevision = data.revision;
            if (message) message.textContent = 'New progress has been saved. Waiting for this worker command to finish before opening the result.';
            timer = setTimeout(check, 4000);
            return;
          }
          stopped = true;
          window.location.replace(window.location.href); // Existing server route authorizes report navigation.
          return;
        }
        if (data.terminal === true && !dispatching) {
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
  if (dispatchForm) {
    dispatchForm.addEventListener('submit', (event) => { event.preventDefault(); dispatchJob(); });
    dispatchJob(); // The preceding research/review POST already authorized this queued job.
  }
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); }, {once: true});
  window.addEventListener('pageshow', (event) => { if (event.persisted) window.location.reload(); });
})();
