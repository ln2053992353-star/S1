/**
 * Application entry point.
 *
 * Orchestrates: fetch → parse → render → mount.
 *
 * To reconnect to a real API, change `dataSource: 'api'` and set `apiEndpoint`.
 */
import { DataProvider } from './utils/dataProvider.js';
import { parseRecommendationData } from './utils/recommendationParser.js';
import { RecommendationReport } from './components/RecommendationReport.js';

(function () {
  var dataProvider = new DataProvider({
    dataSource: 'local',
    localPath: './data/interfaceData.json'
    // Future API usage:
    // dataSource: 'api',
    // apiEndpoint: '/api/recommendation/',
    // apiMethod: 'POST'
  });

  var root = document.getElementById('app');

  function showLoading() {
    root.innerHTML =
      '<div class="max-w-5xl mx-auto px-4 py-10">' +
      '<div class="text-center mb-10">' +
      '<div class="skeleton-pulse h-10 w-96 mx-auto bg-gray-200 rounded mb-3"></div>' +
      '<div class="skeleton-pulse h-5 w-48 mx-auto bg-gray-200 rounded"></div>' +
      '</div>' +
      '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">' +
      '<div class="skeleton-pulse h-24 bg-gray-200 rounded-xl"></div>' +
      '<div class="skeleton-pulse h-24 bg-gray-200 rounded-xl"></div>' +
      '<div class="skeleton-pulse h-24 bg-gray-200 rounded-xl"></div>' +
      '<div class="skeleton-pulse h-24 bg-gray-200 rounded-xl"></div>' +
      '</div>' +
      '<div class="skeleton-pulse h-8 w-48 bg-gray-200 rounded mb-4"></div>' +
      '<div class="skeleton-pulse h-64 bg-gray-200 rounded-2xl"></div>' +
      '</div>';
  }

  function showError(message) {
    root.innerHTML =
      '<div class="flex items-center justify-center min-h-screen px-4">' +
      '<div class="bg-white rounded-2xl shadow-lg p-8 text-center max-w-md w-full">' +
      '<div class="text-red-400 text-5xl mb-4">' +
      '<i class="fas fa-exclamation-triangle"></i>' +
      '</div>' +
      '<h2 class="text-xl font-bold text-gray-900 mb-2">Failed to Load Report</h2>' +
      '<p class="text-gray-500 text-sm mb-6">' +
      escapeHtml(message) +
      '</p>' +
      '<button id="retry-btn" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium transition text-sm">' +
      '<i class="fas fa-redo mr-2"></i>Retry' +
      '</button>' +
      '</div>' +
      '</div>';

    document.getElementById('retry-btn').addEventListener('click', init);
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function init() {
    showLoading();

    dataProvider
      .fetchData()
      .then(function (rawData) {
        var parsed = parseRecommendationData(rawData);
        var reportElement = RecommendationReport.render(parsed);
        root.innerHTML = '';
        root.appendChild(reportElement);

        // Trigger progress bar fill animations after DOM is live
        requestAnimationFrame(function () {
          var fills = root.querySelectorAll('.progress-fill');
          for (var i = 0; i < fills.length; i++) {
            var el = fills[i];
            var target = el.parentNode.getAttribute('aria-valuenow');
            if (target) {
              el.style.width = target + '%';
            }
          }
        });
      })
      .catch(function (err) {
        console.error(err);
        showError(err.message);
      });
  }

  // Bootstrap
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
