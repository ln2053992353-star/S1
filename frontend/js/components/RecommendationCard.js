/**
 * Single recommendation card component.
 *
 * All dynamic text from data is set via textContent — never innerHTML.
 * Fields that are missing/null are omitted gracefully.
 */
export class RecommendationCard {

  /**
   * @param {Object} item  - A single merged recommendation object.
   * @param {number} index - Zero-based position in the list.
   * @returns {HTMLElement}
   */
  static render(item, index) {
    var card = document.createElement('article');
    card.className =
      'bg-white rounded-2xl shadow-sm border border-gray-100 p-6 opacity-0 animate-fade-in-up';
    card.style.animationDelay = (index * 0.08) + 's';

    // Top-recommendation highlight
    if (item.isTop) {
      card.classList.add('ring-2', 'ring-amber-400', 'ring-offset-2');
    }

    // --- Top Recommendation badge ---
    if (item.isTop) {
      card.appendChild(this._buildTopBadge());
    }

    // --- Product Name ---
    var title = document.createElement('h3');
    title.className = 'text-xl font-bold text-gray-900 mb-3';
    title.textContent = item.product_name || 'Unnamed Product';
    card.appendChild(title);

    // --- Evaluation Score (progress bar) ---
    if (item.score != null) {
      card.appendChild(this._buildScoreBar(item.score));
    } else {
      // Omit progress bar; show N/A chip
      var naRow = document.createElement('div');
      naRow.className = 'mb-3 flex items-center gap-2';
      var naLabel = document.createElement('span');
      naLabel.className = 'text-sm font-semibold text-gray-500';
      naLabel.textContent = 'Evaluation Score';
      naRow.appendChild(naLabel);
      var naValue = document.createElement('span');
      naValue.className =
        'text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded';
      naValue.textContent = 'N/A';
      naRow.appendChild(naValue);
      card.appendChild(naRow);
    }

    // --- Semantic Similarity ---
    if (item.similarity != null) {
      card.appendChild(this._buildSimilarity(item.similarity));
    }

    // --- Recommendation Reason ---
    if (item.reason) {
      card.appendChild(this._buildReason(item.reason));
    }

    // --- Functional Description ---
    if (item.description_raw) {
      card.appendChild(this._buildDescription(item.description_raw));
    }

    // --- IUPAC Name ---
    if (item.iupac_name) {
      card.appendChild(this._buildMetaRow('IUPAC Name', item.iupac_name));
    }

    // --- Tags ---
    if (item.tags) {
      card.appendChild(this._buildTags(item.tags));
    }

    // --- DOI ---
    if (item.doi) {
      card.appendChild(this._buildDoiLink(item.doi));
    }

    return card;
  }

  // ------- private helpers -------

  static _buildTopBadge() {
    var wrapper = document.createElement('div');
    wrapper.className = 'mb-3';
    var badge = document.createElement('span');
    badge.className =
      'inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-xs font-bold px-3 py-1 rounded-full';
    badge.textContent = '\u{1F3C6} Top Recommendation';
    wrapper.appendChild(badge);
    return wrapper;
  }

  static _buildScoreBar(score) {
    var clamped = Math.max(0, Math.min(100, score));
    var container = document.createElement('div');
    container.className = 'mb-3';

    var header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-1';

    var label = document.createElement('span');
    label.className = 'text-sm font-semibold text-gray-500';
    label.textContent = 'Evaluation Score';
    header.appendChild(label);

    var value = document.createElement('span');
    value.className = 'text-sm font-bold text-blue-700';
    value.textContent = String(clamped);
    header.appendChild(value);

    container.appendChild(header);

    var track = document.createElement('div');
    track.className = 'w-full bg-gray-200 rounded-full h-2.5';
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-valuenow', String(clamped));
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', '100');

    var fill = document.createElement('div');
    fill.className = 'bg-blue-600 h-2.5 rounded-full progress-fill';
    fill.style.width = '0%';

    // Trigger fill animation after append
    requestAnimationFrame(function () {
      fill.style.width = clamped + '%';
    });

    track.appendChild(fill);
    container.appendChild(track);
    return container;
  }

  static _buildSimilarity(value) {
    var row = document.createElement('div');
    row.className = 'mb-3 flex items-center gap-1 text-sm text-gray-500';

    var icon = document.createElement('i');
    icon.className = 'fas fa-chart-line text-blue-400';
    row.appendChild(icon);

    var label = document.createElement('span');
    label.textContent = 'Semantic Similarity: ';
    row.appendChild(label);

    var num = document.createElement('span');
    num.className = 'font-semibold text-gray-700';
    num.textContent = Number(value).toFixed(4);
    row.appendChild(num);

    return row;
  }

  static _buildReason(reason) {
    var wrapper = document.createElement('div');
    wrapper.className = 'bg-blue-50 border border-blue-100 rounded-lg p-4 mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-blue-600 uppercase tracking-wider mb-1';
    heading.textContent = 'Recommendation Reason';
    wrapper.appendChild(heading);

    var body = document.createElement('p');
    body.className = 'text-sm text-gray-700 leading-relaxed';
    body.textContent = reason;
    wrapper.appendChild(body);

    return wrapper;
  }

  static _buildDescription(raw) {
    var wrapper = document.createElement('div');
    wrapper.className = 'mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-gray-500 uppercase tracking-wider mb-1';
    heading.textContent = 'Functional Description';
    wrapper.appendChild(heading);

    var body = document.createElement('p');
    body.className = 'text-sm text-gray-600 leading-relaxed';
    body.style.whiteSpace = 'pre-line';
    body.textContent = raw;
    wrapper.appendChild(body);

    return wrapper;
  }

  static _buildMetaRow(labelText, value) {
    var row = document.createElement('div');
    row.className = 'mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-gray-500 uppercase tracking-wider mb-1';
    heading.textContent = labelText;
    row.appendChild(heading);

    var body = document.createElement('p');
    body.className = 'text-sm text-gray-600';
    body.textContent = value;
    row.appendChild(body);

    return row;
  }

  static _buildTags(tagsStr) {
    var wrapper = document.createElement('div');
    wrapper.className = 'mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-gray-500 uppercase tracking-wider mb-2';
    heading.textContent = 'Tags';
    wrapper.appendChild(heading);

    var container = document.createElement('div');
    container.className = 'flex flex-wrap gap-2';

    var tagList = tagsStr.split(';');
    for (var i = 0; i < tagList.length; i++) {
      var t = tagList[i].trim();
      if (!t) continue;
      var chip = document.createElement('span');
      chip.className =
        'bg-gray-100 text-gray-600 border border-gray-200 px-2.5 py-0.5 rounded-lg text-xs font-medium';
      chip.textContent = t;
      container.appendChild(chip);
    }
    wrapper.appendChild(container);

    return wrapper;
  }

  static _buildDoiLink(doi) {
    var row = document.createElement('div');
    row.className = 'mt-4 pt-3 border-t border-gray-100';

    var icon = document.createElement('i');
    icon.className = 'fas fa-book text-blue-400 mr-1';
    row.appendChild(icon);

    var link = document.createElement('a');
    link.className =
      'text-sm text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1';
    link.href = 'https://doi.org/' + doi;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = doi;
    row.appendChild(link);

    var extIcon = document.createElement('i');
    extIcon.className = 'fas fa-external-link-alt text-xs ml-1 text-blue-400';
    row.appendChild(extIcon);

    return row;
  }
}
