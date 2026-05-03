import { RecommendationCard } from './RecommendationCard.js';

/**
 * Top-level report layout.
 * Renders: title, info card grid, warning banner, recommendation list.
 *
 * All dynamic text from data is set via textContent — never innerHTML.
 */
export class RecommendationReport {

  /**
   * @param {{ formatter: Object, recommendations: Array, warning: string|null }} parsedData
   * @returns {HTMLElement}
   */
  static render(parsedData) {
    var container = document.createElement('div');
    container.className = 'max-w-5xl mx-auto px-4 py-10';

    // --- Title ---
    container.appendChild(this._buildTitle(parsedData.formatter));

    // --- Warning banner ---
    if (parsedData.warning) {
      container.appendChild(this._buildWarning(parsedData.warning));
    }

    // --- Info cards ---
    container.appendChild(this._buildInfoGrid(parsedData.formatter));

    // --- Divider ---
    var divider = document.createElement('hr');
    divider.className = 'my-8 border-gray-200';
    container.appendChild(divider);

    // --- Recommendations ---
    container.appendChild(
      this._buildRecommendationList(
        parsedData.recommendations,
        parsedData.warning
      )
    );

    return container;
  }

  // ------- private helpers -------

  static _buildTitle(formatter) {
    var header = document.createElement('header');
    header.className = 'text-center mb-10';

    var h1 = document.createElement('h1');
    h1.className =
      'text-3xl md:text-4xl font-extrabold text-gray-900 mb-2 tracking-tight';
    h1.textContent = 'Biochemical Product Recommendation Report';
    header.appendChild(h1);

    var sub = document.createElement('p');
    sub.className = 'text-gray-500 text-sm';
    var countText =
      formatter.iterationCount != null
        ? 'Iterations: ' + formatter.iterationCount
        : '';
    sub.textContent = countText;
    header.appendChild(sub);

    return header;
  }

  static _buildWarning(message) {
    var banner = document.createElement('div');
    banner.className =
      'bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 flex items-start gap-3';

    var icon = document.createElement('i');
    icon.className = 'fas fa-exclamation-triangle text-amber-500 mt-0.5';
    banner.appendChild(icon);

    var text = document.createElement('p');
    text.className = 'text-sm text-amber-800';
    text.textContent = message;
    banner.appendChild(text);

    return banner;
  }

  static _buildInfoGrid(formatter) {
    var grid = document.createElement('div');
    grid.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4';

    grid.appendChild(
      this._buildInfoCard(
        'User Input',
        formatter.rawInput,
        'fas fa-user-edit',
        'text-blue-600'
      )
    );
    grid.appendChild(
      this._buildInfoCard(
        'Refined Input',
        formatter.refinedInput,
        'fas fa-microscope',
        'text-purple-600'
      )
    );
    grid.appendChild(
      this._buildInfoCard(
        'Verification Score',
        formatter.verificationScore != null
          ? String(formatter.verificationScore)
          : 'N/A',
        'fas fa-check-circle',
        this._verificationColor(formatter.verificationScore)
      )
    );
    grid.appendChild(
      this._buildInfoCard(
        'Iteration Count',
        formatter.iterationCount != null
          ? String(formatter.iterationCount)
          : '0',
        'fas fa-redo-alt',
        'text-teal-600'
      )
    );

    return grid;
  }

  static _buildInfoCard(label, value, iconClass, iconColor) {
    var card = document.createElement('div');
    card.className =
      'bg-white rounded-xl shadow-sm border border-gray-100 p-5 opacity-0 animate-fade-in-up';
    card.style.animationDelay = '0.05s';

    var header = document.createElement('div');
    header.className = 'flex items-center gap-2 mb-2';

    var icon = document.createElement('i');
    icon.className = iconClass + ' ' + iconColor;
    header.appendChild(icon);

    var heading = document.createElement('h4');
    heading.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider';
    heading.textContent = label;
    header.appendChild(heading);

    card.appendChild(header);

    var body = document.createElement('p');
    body.className = 'text-sm text-gray-800 leading-relaxed';
    body.style.whiteSpace = 'pre-line';
    body.textContent = value;
    card.appendChild(body);

    return card;
  }

  static _verificationColor(score) {
    if (score == null) return 'text-gray-400';
    if (score >= 80) return 'text-green-600';
    if (score >= 50) return 'text-amber-600';
    return 'text-red-600';
  }

  static _buildRecommendationList(recommendations, warning) {
    var section = document.createElement('section');

    // Section header
    var header = document.createElement('div');
    header.className = 'mb-6';

    var h2 = document.createElement('h2');
    h2.className = 'text-2xl font-bold text-gray-900';
    h2.textContent = 'Recommendations';

    var count = document.createElement('span');
    count.className = 'ml-2 text-gray-400 text-lg font-normal';
    count.textContent = '(' + recommendations.length + ')';
    h2.appendChild(count);
    header.appendChild(h2);

    // If we're in fallback mode, add a label
    if (warning) {
      var badge = document.createElement('span');
      badge.className =
        'inline-block mt-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded';
      badge.textContent = 'Fallback mode';
      header.appendChild(badge);
    }

    section.appendChild(header);

    // Empty state
    if (recommendations.length === 0) {
      var empty = document.createElement('div');
      empty.className =
        'text-center py-16 bg-white rounded-2xl border border-dashed border-gray-300';

      var emptyIcon = document.createElement('i');
      emptyIcon.className = 'fas fa-inbox text-gray-300 text-6xl mb-4';
      empty.appendChild(emptyIcon);

      var emptyText = document.createElement('p');
      emptyText.className = 'text-lg text-gray-500';
      emptyText.textContent = 'No recommendations found for this query.';
      empty.appendChild(emptyText);

      section.appendChild(empty);
      return section;
    }

    // Card list
    var list = document.createElement('div');
    list.className = 'space-y-6';
    for (var i = 0; i < recommendations.length; i++) {
      list.appendChild(RecommendationCard.render(recommendations[i], i));
    }
    section.appendChild(list);

    return section;
  }
}
