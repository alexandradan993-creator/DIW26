/* Contrat unique : données d'une version immuable, fiches par EGRID. */
(() => {
  let version = null;
  let following = null;
  let busy = false;
  let message = 'Prêt à actualiser les données.';
  const banner = document.querySelector('#applicationStatus');
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function api(path, options = {}) {
    if (!['http:', 'https:'].includes(location.protocol)) {
      throw new Error('Ouvrez cette interface depuis le serveur Python, à http://127.0.0.1:8000/.');
    }
    const response = await fetch(path, {...options, signal: AbortSignal.timeout(20000), cache: 'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.erreur || `Réponse serveur ${response.status}`);
    return data;
  }

  function status(text, pending = busy) {
    message = text;
    busy = pending;
    const button = document.querySelector('#refreshData');
    const label = document.querySelector('#refreshStatus');
    if (label) label.textContent = text;
    if (button) {
      button.disabled = pending;
      button.setAttribute('aria-busy', String(pending));
    }
  }

  async function reload() {
    const data = await api('/application/donnees');
    if (data.schema_version !== 2 || !data.version || !Array.isArray(data.parcels) || data.parcels.length !== data.total) {
      throw new Error('Export de la version serveur incomplet. Affichage précédent conservé.');
    }
    if (data.parcels.some(row => !Array.isArray(row) || row.length !== 10 || !Array.isArray(row[6])
      || row[6].length !== 10 || !Array.isArray(row[6][7]) || row[6][7].length !== 19)) {
      throw new Error('Format des fiches incompatible. Affichage précédent conservé.');
    }
    const ids = data.parcels.map(row => row[1]);
    if (ids.some(id => !id) || new Set(ids).size !== ids.length) throw new Error('EGRID absents ou dupliqués.');
    // Tout préparer avant de remplacer les données communes de Carte et Liste.
    const hidden = new Set(data.masquees_par_defaut || []);
    const next = data.parcels.filter(row => !hidden.has(row[1])).map(makeShape);
    const chosen = selected?.egrid;
    const panelState = Object.fromEntries(['inlineSearch','inlineStatus','contactFilter','decisionFilter'].map(id => [id, document.getElementById(id)?.value]));
    shapes.splice(0, shapes.length, ...next);
    for (const key of Object.keys(parcelAddresses)) delete parcelAddresses[key];
    for (const key of Object.keys(filterMeasures)) delete filterMeasures[key];
    Object.assign(parcelAddresses, data.addresses);
    Object.assign(filterMeasures, data.measures);
    version = data.version;
    selected = shapes.find(row => row.egrid === chosen) || null;
    if (document.querySelector('#details').open) document.querySelector('#details').close();
    // Un dossier en cours de saisie reste ouvert : ne pas perdre ses champs non enregistrés.
    selectParcel(selected);
    if (activeTab === 'list' || activeTab === 'saved') {
      renderInline(activeTab === 'saved');
      for (const [id, value] of Object.entries(panelState)) {
        const control = document.getElementById(id);
        if (control && value != null) control.value = value;
      }
      document.getElementById('inlineSearch')?.dispatchEvent(new Event('input'));
    }
    banner.textContent = `${data.total.toLocaleString('fr-CH')} parcelles · ${next.length.toLocaleString('fr-CH')} affichées · version ${version} · notes personnelles conservées`;
    banner.title = version;
  }

  async function follow(id) {
    following = id;
    const deadline = Date.now() + 30 * 60 * 1000;
    try {
      while (Date.now() < deadline) {
        const state = await api(`/actualisations/${encodeURIComponent(id)}`);
        if (state.statut === 'erreur') throw new Error(state.erreur || 'Échec de l’actualisation.');
        if (['termine', 'aucun_changement'].includes(state.statut)) {
          await reload();
          const alerts = state.alertes?.length ? `\nÀ signaler : ${state.alertes.join(' · ')}` : '';
          status((state.statut === 'aucun_changement'
            ? 'Vérification terminée : aucun changement des données.'
            : 'Actualisation terminée. La Carte et la Liste utilisent la nouvelle version.') + alerts, false);
          return;
        }
        status(`Actualisation en cours : ${state.etape || 'traitement serveur'}. Vous pouvez continuer à consulter la version active.`, true);
        await pause(1500);
      }
      throw new Error('Le suivi est en pause après 30 minutes. Cliquez à nouveau pour reprendre le suivi du même traitement.');
    } catch (error) {
      status(`${error.message}\nLa dernière version affichée est conservée. Le traitement serveur peut continuer ; cliquez pour reprendre son suivi.`, false);
    } finally {
      following = null;
    }
  }

  async function start() {
    if (busy || following) return;
    status('Connexion au serveur d’actualisation…', true);
    try {
      // Retrouver une tâche en cours, y compris après rechargement de la page.
      const current = await api('/actualisations/etat');
      if (current.statut === 'en_cours' && current.operation_id) {
        await follow(current.operation_id);
        return;
      }
      const operation = await api('/actualisations', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
      });
      if (!operation.operation_id) throw new Error('Identifiant de traitement manquant.');
      await follow(operation.operation_id);
    } catch (error) {
      status(`Actualisation non confirmée : ${error.message}\nCliquez pour retrouver un éventuel traitement en cours.`, false);
    }
  }

  async function fiche(egrid) {
    try {
      const data = await api(`/parcelles/${encodeURIComponent(egrid)}?version=${encodeURIComponent(version || '')}`);
      if (data.egrid !== egrid || data.version !== version) throw new Error('Version de fiche incohérente.');
      return data;
    } catch (error) {
      banner.textContent = `Fiche serveur indisponible : ${error.message}`;
      return null;
    }
  }

  function contraintes(data, container) {
    const section = document.createElement('section');
    section.className = 'parcelFacts';
    const title = document.createElement('h3');
    title.textContent = 'Observations cantonales actualisées';
    section.append(title);
    if (!data) {
      const p = document.createElement('p');
      p.textContent = 'Fiche serveur indisponible : contraintes à vérifier.';
      section.append(p); container.append(section); return;
    }
    const definitions = [
      ['isos_presence', 'Dans un périmètre cantonal fondé sur l’ISOS'],
      ['isos_part_parcelle_pct', 'Part recouverte par les périmètres ISOS'],
      ['isos_objets', 'Sites ISOS rencontrés'],
      ['isos_surface_m2', 'Surface recouverte par les périmètres ISOS'],
      ['dangers_presence', 'Danger naturel identifié'],
      ['dangers_classes', 'Classes de danger rencontrées'],
      ['danger_part_risque_pct', 'Part recouverte par un danger identifié'],
      ['dangers_couverture_pct', 'Couverture de l’étude des dangers'],
      ['danger_nul_etudie', 'Danger nul confirmé sur toute la parcelle']
    ];
    const dl = document.createElement('dl');
    for (const [key, label] of definitions) {
      const field = data.contraintes[key];
      if (!field) continue;
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd');
      const v = field.valeur;
      const summary = item => {
        if (typeof item !== 'object' || item === null) return String(item);
        const name = item.attributs?.NOM_SITE || item.libelle || item.valeur_metier || item.code || 'Objet';
        const part = item.part_parcelle_pct == null ? '' : ` (${Number(item.part_parcelle_pct).toLocaleString('fr-CH', {maximumFractionDigits: 2})} %)`;
        return name + part;
      };
      const text = v == null ? 'À vérifier' : typeof v === 'boolean' ? (v ? 'Oui' : 'Non')
        : typeof v === 'number' ? v.toLocaleString('fr-CH', {maximumFractionDigits: 2})
        : Array.isArray(v) ? (v.map(summary).join(' · ') || 'Aucune classe rencontrée') : String(v);
      dd.textContent = text + (v != null && field.unite ? ` ${field.unite}` : '');
      const source = document.createElement('small'); source.className = 'observationSource';
      source.textContent = [field.motif, `État : ${field.etat}`,
        field.date_verification ? `Vérifié le ${new Date(field.date_verification).toLocaleString('fr-CH', {timeZone: 'Europe/Zurich'})}` : 'Non encore vérifié',
        field.date_donnee ? `Donnée : ${field.date_donnee}` : 'Date de la donnée non renseignée'].filter(Boolean).join(' · ');
      dd.append(source);
      if (field.source?.url) {
        const link = document.createElement('a'); link.href = field.source.url;
        link.textContent = 'Source officielle';link.target = '_blank';link.rel = 'noopener noreferrer';dd.append(link);
      }
      dl.append(dt, dd);
    }
    section.append(dl); container.append(section);
  }

  window.foncimoActualisation = {
    mount(button, label) {label.textContent = message;status(message, busy);},
    start,
    fiche, contraintes
  };
  reload().catch(error => {
    banner.textContent = `Données serveur indisponibles : ${error.message}`;
    status(banner.textContent, false);
  });
})();
