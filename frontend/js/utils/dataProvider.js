/**
 * Data access abstraction layer.
 *
 * Local mode: fetches a JSON file from a relative path.
 * API mode (future):  POSTs/GETs to a live endpoint.
 *
 * To reconnect to a real API later, change `dataSource` to 'api'
 * and provide `apiEndpoint` in the App constructor (app.js).
 */
export class DataProvider {
  constructor(config = {}) {
    this.config = {
      dataSource: 'local',
      localPath: './data/interfaceData.json',
      apiEndpoint: null,
      apiMethod: 'GET',
      apiHeaders: { 'Content-Type': 'application/json' },
      timeout: 10000,
      ...config
    };
  }

  async fetchData() {
    if (this.config.dataSource === 'local') {
      return this._fetchLocal();
    }
    if (this.config.dataSource === 'api') {
      return this._fetchApi();
    }
    throw new Error('Unknown dataSource: ' + this.config.dataSource);
  }

  async _fetchLocal() {
    let response;
    try {
      response = await fetch(this.config.localPath);
    } catch (e) {
      throw new Error(
        'Failed to load local data file "' +
          this.config.localPath +
          '". Ensure the module is served over HTTP (e.g. python -m http.server 8080).'
      );
    }

    if (!response.ok) {
      throw new Error(
        'Failed to load data: HTTP ' + response.status + ' ' + response.statusText
      );
    }

    let data;
    try {
      data = await response.json();
    } catch (e) {
      throw new Error('Data file is not valid JSON: ' + e.message);
    }
    return data;
  }

  async _fetchApi() {
    const controller = new AbortController();
    const timeoutId = setTimeout(function () {
      controller.abort();
    }, this.config.timeout);

    let response;
    try {
      response = await fetch(this.config.apiEndpoint, {
        method: this.config.apiMethod,
        headers: this.config.apiHeaders,
        signal: controller.signal
      });
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') {
        throw new Error('Request timed out after ' + this.config.timeout + 'ms');
      }
      throw new Error('API request failed: ' + e.message);
    }
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(
        'API error: HTTP ' + response.status + ' ' + response.statusText
      );
    }

    let data;
    try {
      data = await response.json();
    } catch (e) {
      throw new Error('API response is not valid JSON: ' + e.message);
    }
    return data;
  }
}
