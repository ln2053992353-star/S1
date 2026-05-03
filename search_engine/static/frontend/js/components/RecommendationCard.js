/**
 * Single recommendation card component.
 *
 * All dynamic text from JSON is set via textContent — never innerHTML.
 * Fields that are missing/null are omitted gracefully.
 *
 * Expects camelCase fields from recommendationParser.js.
 */
export class RecommendationCard {

  /**
   * @param {Object} item  - Merged recommendation (camelCase).
   * @param {number} index - Zero-based position in the list.
   * @returns {HTMLElement}
   */
  static render(item, index) {
    var card = document.createElement('article');
    card.className =
      'bg-white rounded-2xl shadow-sm border border-gray-100 p-6 opacity-0 animate-fade-in-up';
    card.style.animationDelay = (index * 0.08) + 's';

    if (item.isTop) {
      card.classList.add('ring-2', 'ring-amber-400', 'ring-offset-2');
    }

    // 1. Top Recommendation badge
    if (item.isTop) {
      card.appendChild(this._buildTopBadge());
    }

    // 2. Product Name
    card.appendChild(this._buildProductName(item.productName));

    // 3. Evaluation Score
    if (item.evaluationScore != null) {
      card.appendChild(this._buildScoreBar(item.evaluationScore));
    } else {
      card.appendChild(this._buildScoreNA());
    }

    // 4. Semantic Similarity
    if (item.semanticSimilarity != null) {
      card.appendChild(this._buildSimilarity(item.semanticSimilarity));
    }

    // 5. Recommendation Reason
    if (item.recommendationReason) {
      card.appendChild(this._buildReason(item.recommendationReason));
    }

    // 6. Functional Description (clean, w/o PubChem block)
    var displayDesc = item.functionalDescriptionClean || item.descriptionRaw;
    if (displayDesc) {
      card.appendChild(this._buildDescription(displayDesc));
    }

    // 7. PubChem Data block
    if (item.iupacName || item.pubchemCid || item.pubchemDescription || item.tags) {
      card.appendChild(this._buildPubChemSection(item));
    }

    // 8. DOI
    if (item.doi) {
      card.appendChild(this._buildDoiLink(item.doi));
    }

    return card;
  }

  /* ── section builders ──────────────────────────────── */

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

  static _buildProductName(name) {
    var h3 = document.createElement('h3');
    h3.className = 'text-xl font-bold text-gray-900 mb-3';
    h3.textContent = name || 'Unnamed Product';
    return h3;
  }

  /* ── score ─────────────────────────────────────────── */

  static _buildScoreNA() {
    var row = document.createElement('div');
    row.className = 'mb-3 flex items-center gap-2';
    var label = document.createElement('span');
    label.className = 'text-sm font-semibold text-gray-500';
    label.textContent = 'Evaluation Score';
    row.appendChild(label);
    var chip = document.createElement('span');
    chip.className =
      'text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded';
    chip.textContent = 'N/A';
    row.appendChild(chip);
    return row;
  }

  static _buildScoreBar(score) {
    var clamped = Math.max(0, Math.min(100, Number(score) || 0));
    var colorClasses = this._scoreColor(clamped);

    var container = document.createElement('div');
    container.className = 'mb-3';

    var header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-1';

    var label = document.createElement('span');
    label.className = 'text-sm font-semibold text-gray-500';
    label.textContent = 'Evaluation Score';
    header.appendChild(label);

    var value = document.createElement('span');
    value.className = 'text-sm font-bold ' + colorClasses.text;
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
    fill.className = colorClasses.bar + ' h-2.5 rounded-full progress-fill';
    fill.style.width = '0%';

    requestAnimationFrame(function () {
      fill.style.width = clamped + '%';
    });

    track.appendChild(fill);
    container.appendChild(track);
    return container;
  }

  static _scoreColor(clamped) {
    if (clamped >= 80) return { text: 'text-green-700', bar: 'bg-green-500' };
    if (clamped >= 50) return { text: 'text-amber-700', bar: 'bg-amber-500' };
    return { text: 'text-red-600', bar: 'bg-red-400' };
  }

  /* ── similarity ────────────────────────────────────── */

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

  /* ── reason ────────────────────────────────────────── */

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

  /* ── functional description ────────────────────────── */

  static _buildDescription(text) {
    var wrapper = document.createElement('div');
    wrapper.className = 'mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-gray-500 uppercase tracking-wider mb-1';
    heading.textContent = 'Functional Description';
    wrapper.appendChild(heading);

    var body = document.createElement('pre');
    body.className =
      'text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-xl p-4 leading-relaxed';
    body.style.whiteSpace = 'pre-line';
    body.textContent = text;
    wrapper.appendChild(body);

    return wrapper;
  }

  /* ── PubChem Data section ──────────────────────────── */

  static _buildPubChemSection(item) {
    var wrapper = document.createElement('div');
    wrapper.className =
      'bg-white border border-indigo-200 rounded-xl p-4 mb-3';

    var heading = document.createElement('div');
    heading.className =
      'text-xs font-bold text-indigo-600 uppercase tracking-wider mb-3';
    heading.textContent = 'PubChem Data';
    wrapper.appendChild(heading);

    if (item.iupacName) {
      wrapper.appendChild(this._pubChemRow('IUPAC', item.iupacName));
    }
    if (item.pubchemCid) {
      wrapper.appendChild(this._pubChemRow('PubChem CID', item.pubchemCid));
    }
    if (item.pubchemDescription) {
      wrapper.appendChild(this._pubChemRow('PubChem Description', item.pubchemDescription));
    }
    if (item.tags) {
      wrapper.appendChild(this._pubChemTags(item.tags));
    }

    return wrapper;
  }

  static _pubChemRow(labelText, value) {
    var row = document.createElement('div');
    row.className = 'mb-2 last:mb-0';

    var label = document.createElement('span');
    label.className = 'text-xs font-semibold text-gray-500 mr-2';
    label.textContent = labelText + ':';
    row.appendChild(label);

    var val = document.createElement('span');
    val.className = 'text-sm text-gray-700';
    val.textContent = value;
    row.appendChild(val);

    return row;
  }

  static _pubChemTags(tagsStr) {
    var row = document.createElement('div');
    row.className = 'mb-2 last:mb-0';

    var label = document.createElement('span');
    label.className = 'text-xs font-semibold text-gray-500 mr-2';
    label.textContent = 'Tags:';
    row.appendChild(label);

    var container = document.createElement('span');
    container.className = 'inline-flex flex-wrap gap-1.5';

    var tagList = tagsStr.split(';');
    for (var i = 0; i < tagList.length; i++) {
      var t = tagList[i].trim();
      if (!t) continue;
      var chip = document.createElement('span');
      chip.className =
        'bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded text-xs font-medium';
      chip.textContent = t;
      container.appendChild(chip);
    }
    row.appendChild(container);

    return row;
  }

  /* ── DOI link ──────────────────────────────────────── */

  static _buildDoiLink(doi) {
    var row = document.createElement('div');
    row.className = 'mt-4 pt-3 border-t border-gray-100';

    var icon = document.createElement('i');
    icon.className = 'fas fa-book text-blue-400 mr-1';
    row.appendChild(icon);

    var label = document.createElement('span');
    label.className = 'text-sm text-gray-500 mr-1';
    label.textContent = 'DOI:';
    row.appendChild(label);

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
