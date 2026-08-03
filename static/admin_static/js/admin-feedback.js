(function (window, document) {
  'use strict';

  var notyf = window.Notyf ? new window.Notyf({
    duration: 4500,
    dismissible: true,
    position: { x: 'right', y: 'top' },
    ripple: true,
    types: [
      { type: 'info', background: '#3498db' },
      { type: 'warning', background: '#f0ad4e' }
    ]
  }) : null;

  function toPlainText(value) {
    var parsed = new window.DOMParser().parseFromString(
      String(value || ''),
      'text/html'
    );
    return (parsed.body.textContent || '').trim();
  }

  function fallbackToast(type, message, duration) {
    var container = document.querySelector('.admin-fallback-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'admin-fallback-toast-container';
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'admin-fallback-toast admin-fallback-toast--' + type;
    toast.textContent = message;
    container.appendChild(toast);
    window.setTimeout(function () { toast.remove(); }, duration || 4500);
    return toast;
  }

  function notify(type, message, options) {
    options = options || {};
    var text = toPlainText(message);
    if (!text) {
      return null;
    }

    if (!notyf) {
      return fallbackToast(type, text, options.duration);
    }

    var notification = { message: text };
    if (options.duration) {
      notification.duration = options.duration;
    }

    if (type === 'success') {
      return notyf.success(notification);
    }
    if (type === 'error') {
      return notyf.error(notification);
    }
    notification.type = type;
    return notyf.open(notification);
  }

  function loaderElement() {
    return document.getElementById('admin-operation-loader');
  }

  function showLoading() {
    var loader = loaderElement();
    if (!loader) {
      return;
    }
    loader.classList.add('is-visible');
    loader.setAttribute('aria-hidden', 'false');
  }

  function hideLoading() {
    var loader = loaderElement();
    if (!loader) {
      return;
    }
    loader.classList.remove('is-visible');
    loader.setAttribute('aria-hidden', 'true');
  }

  function csrfToken() {
    var token = document.querySelector('meta[name="admin-csrf-token"]');
    if (token && token.content) {
      return token.content;
    }
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function errorMessage(payload, fallback) {
    if (!payload) {
      return fallback;
    }
    return payload.message || payload.detail || payload.error || fallback;
  }

  function reloadContainingTable(trigger) {
    if (!window.jQuery || !window.jQuery.fn.DataTable) {
      return;
    }
    var tableElement = trigger.closest('table');
    if (
      tableElement &&
      window.jQuery.fn.DataTable.isDataTable(tableElement)
    ) {
      var dataTable = window.jQuery(tableElement).DataTable();
      var settings = dataTable.settings()[0];
      if (settings && settings.ajax) {
        dataTable.ajax.reload(null, false);
      } else {
        dataTable.row(trigger.closest('tr')).remove().draw(false);
      }
      return;
    }

    var row = trigger.closest('tr');
    if (row) {
      row.remove();
    }
  }

  function deleteRecord(trigger) {
    var deleteUrl = trigger.dataset.deleteUrl;
    var fallback = trigger.dataset.deleteError || 'The record could not be deleted. Please try again.';

    showLoading();
    trigger.setAttribute('aria-disabled', 'true');

    window.fetch(deleteUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (payload) {
        if (!response.ok) {
          var requestError = new Error(errorMessage(payload, fallback));
          requestError.payload = payload;
          throw requestError;
        }
        return payload;
      });
    }).then(function (payload) {
      notify('success', payload.message || 'The record was deleted successfully.');
      reloadContainingTable(trigger);
    }).catch(function (requestError) {
      notify('error', requestError.message || fallback, { duration: 6500 });
    }).finally(function () {
      trigger.removeAttribute('aria-disabled');
      hideLoading();
    });
  }

  function handleDeleteClick(event) {
    var trigger = event.target.closest('.admin-delete-trigger');
    if (!trigger) {
      return;
    }

    event.preventDefault();
    if (trigger.getAttribute('aria-disabled') === 'true') {
      return;
    }

    if (window.jQuery) {
      window.jQuery('[data-toggle="tooltip"]').tooltip('hide');
    }

    var now = Date.now();
    var confirmedUntil = Number(trigger.dataset.adminConfirmedUntil || 0);
    if (confirmedUntil > now) {
      delete trigger.dataset.adminConfirmedUntil;
      deleteRecord(trigger);
      return;
    }

    var label = trigger.dataset.deleteLabel || trigger.dataset.deleteTitle ||
      trigger.dataset.deleteName || 'this record';
    trigger.dataset.adminConfirmedUntil = String(now + 5000);
    notify(
      'warning',
      'Click Delete again within 5 seconds to permanently delete ' + label + '.',
      { duration: 5000 }
    );

    window.setTimeout(function () {
      if (Number(trigger.dataset.adminConfirmedUntil || 0) <= Date.now()) {
        delete trigger.dataset.adminConfirmedUntil;
      }
    }, 5100);
  }

  function consumeDjangoMessages() {
    document.querySelectorAll('[data-admin-message]').forEach(function (element) {
      var tags = (element.dataset.messageTags || 'info').toLowerCase();
      var type = tags.indexOf('error') !== -1 ? 'error' :
        tags.indexOf('success') !== -1 ? 'success' :
          tags.indexOf('warning') !== -1 ? 'warning' : 'info';
      notify(type, element.textContent, { duration: type === 'error' ? 6500 : 4500 });
    });

    if (document.querySelector('.errorlist')) {
      notify('error', 'Please correct the highlighted fields and try again.', { duration: 6500 });
    }
  }

  document.addEventListener('click', handleDeleteClick);

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!(form instanceof window.HTMLFormElement) || form.dataset.adminAjax === 'true') {
      return;
    }
    window.setTimeout(function () {
      if (!event.defaultPrevented) {
        showLoading();
      }
    }, 0);
  });

  document.addEventListener('DOMContentLoaded', consumeDjangoMessages);
  window.addEventListener('pageshow', hideLoading);

  window.AdminUI = {
    error: function (message, options) { return notify('error', message, options); },
    errorMessage: errorMessage,
    hideLoading: hideLoading,
    info: function (message, options) { return notify('info', message, options); },
    showLoading: showLoading,
    success: function (message, options) { return notify('success', message, options); },
    warning: function (message, options) { return notify('warning', message, options); }
  };
})(window, document);
