/**
 * Regelwerk und Scores fuer die Befundung.
 *
 * Alle Aussagen entstehen aus den Kennzahlen, die core/strategy.js aus den
 * Gates berechnet. Das Ergebnis ist ein Vorschlag zur Entscheidungsunter-
 * stuetzung, der von einer fachaerztlich qualifizierten Person zu pruefen,
 * zu ergaenzen und zu verantworten ist. Die Software trifft keine Diagnose.
 */

import { ENTITAETEN, erwartung } from './entities.js';
import { bewerte as bewerteReferenz, alterBestimmen, REFERENZBEREICHE } from './reference.js';

const KLASSE_RANG = { negativ: 0, schwach: 1, positiv: 2, stark: 3 };

/** Prueft, ob eine gemessene Klasse zu einer Erwartung passt. */
function passt(klasse, erwartet) {
  if (!erwartet || !klasse || KLASSE_RANG[klasse] === undefined) return null;
  const r = KLASSE_RANG[klasse];
  switch (erwartet) {
    case '++':
      return r === 3;
    case '+':
      return r >= 2;
    case '(+)':
      return r === 1;
    case '+/-':
      return true;
    case '-':
      return r === 0;
    default:
      return null;
  }
}

/* ================================================================== */
/* Scores                                                             */
/* ================================================================== */

export const SCORES = {
  /* ---------------------------------------------------------------- */
  matutes: {
    id: 'matutes',
    name: 'Matutes-Score (CLL)',
    quelle: 'Matutes et al. 1994, modifiziert nach Moreau et al. 1997',
    berechne(ctx) {
      const ziel = ctx.stepGates.cd5b ? 'cd5b' : 'bzell';
      const cd5 = ctx.expression(ziel, 'CD5');
      const cd23 = ctx.expression(ziel, 'CD23');
      const fmc7 = ctx.expression(ziel, 'FMC7');
      const cd22 = ctx.expression(ziel, 'CD22');
      const cd79b = ctx.expression(ziel, 'CD79b');
      const kappa = ctx.expression(ziel, 'Kappa');
      const lambda = ctx.expression(ziel, 'Lambda');

      // Oberflaechen-Immunglobulin: die staerkere der beiden Leichtketten
      const sIgDelta = Math.max(
        Number.isFinite(kappa.delta) ? kappa.delta : -Infinity,
        Number.isFinite(lambda.delta) ? lambda.delta : -Infinity,
      );
      const sIgKlasse = !Number.isFinite(sIgDelta) || sIgDelta === -Infinity
        ? null
        : sIgDelta < 0.2 ? 'schwach' : sIgDelta < 0.42 ? 'positiv' : 'stark';

      const kriterien = [
        { name: 'CD5 positiv', erfuellt: KLASSE_RANG[cd5.level] >= 2, wert: cd5.level, gemessen: cd5.vorhanden },
        { name: 'CD23 positiv', erfuellt: KLASSE_RANG[cd23.level] >= 2, wert: cd23.level, gemessen: cd23.vorhanden },
        { name: 'FMC7 negativ', erfuellt: cd7Negativ(fmc7), wert: fmc7.level, gemessen: fmc7.vorhanden },
        { name: 'sIg schwach', erfuellt: sIgKlasse === 'schwach', wert: sIgKlasse || 'nicht gemessen', gemessen: !!sIgKlasse },
        {
          name: 'CD22 oder CD79b schwach/negativ',
          erfuellt: schwachOderNeg(cd79b) || schwachOderNeg(cd22),
          wert: `CD79b ${cd79b.level}, CD22 ${cd22.level}`,
          gemessen: cd79b.vorhanden || cd22.vorhanden,
        },
      ];

      const gemessene = kriterien.filter((k) => k.gemessen);
      const punkte = kriterien.filter((k) => k.gemessen && k.erfuellt).length;
      const maximum = gemessene.length;

      let bewertung;
      if (maximum < 4) bewertung = 'nicht beurteilbar';
      else if (punkte >= 4) bewertung = 'vereinbar mit CLL';
      else if (punkte === 3) bewertung = 'grenzwertig';
      else bewertung = 'gegen CLL sprechend';

      return {
        punkte,
        maximum,
        kriterien,
        bewertung,
        text:
          maximum < 4
            ? `Matutes-Score nicht beurteilbar: nur ${maximum} von 5 Kriterien messbar (fehlende Marker im Panel).`
            : `Matutes-Score ${punkte} von ${maximum} -- ${bewertung}. ` +
              (punkte >= 4
                ? 'Ein Score von 4-5 Punkten spricht für eine CLL.'
                : punkte === 3
                  ? 'Bei 3 Punkten ist die Abgrenzung zu anderen B-Zell-Lymphomen offen; CD200, Cyclin D1 bzw. t(11;14) ergänzen.'
                  : 'Ein Score von 0-2 Punkten spricht gegen eine CLL; weitere Abklärung erforderlich.'),
      };
    },
  },

  /* ---------------------------------------------------------------- */
  ogata: {
    id: 'ogata',
    name: 'Ogata-Score (MDS)',
    quelle: 'Ogata et al. 2009; Della Porta et al. 2012',
    berechne(ctx, metriken) {
      const wert = (id) => metriken.find((m) => m.id === id)?.wert;
      const cd34 = wert('cd34_pct');
      const bvorl = wert('bvorl_pct');
      const sscRatio = wert('ssc_ratio');
      const cd45Ratio = wert('cd45_ratio');

      const kriterien = [
        {
          name: 'CD34+ Vorläuferzellen ≥ 2 % der kernhaltigen Zellen',
          erfuellt: cd34 >= 2,
          wert: fmt(cd34, 2, ' %'),
          gemessen: Number.isFinite(cd34),
        },
        {
          name: 'B-Vorläufer < 5 % der CD34+ Zellen',
          erfuellt: bvorl < 5,
          wert: fmt(bvorl, 1, ' %'),
          gemessen: Number.isFinite(bvorl),
        },
        {
          name: 'SSC-Quotient Granulozyten/Lymphozyten < 6',
          erfuellt: sscRatio < 6,
          wert: fmt(sscRatio, 2),
          gemessen: Number.isFinite(sscRatio),
        },
        {
          name: 'CD45-Quotient Lymphozyten/Blasten außerhalb 4,0–7,5',
          erfuellt: Number.isFinite(cd45Ratio) && (cd45Ratio < 4 || cd45Ratio > 7.5),
          wert: fmt(cd45Ratio, 2),
          gemessen: Number.isFinite(cd45Ratio),
        },
      ];

      const gemessene = kriterien.filter((k) => k.gemessen);
      const punkte = gemessene.filter((k) => k.erfuellt).length;
      const bewertung = gemessene.length < 4 ? 'unvollstaendig' : punkte >= 2 ? 'MDS-verdächtig' : 'unauffaellig';

      return {
        punkte,
        maximum: gemessene.length,
        kriterien,
        bewertung,
        text:
          gemessene.length < 4
            ? `Ogata-Score unvollständig (${gemessene.length} von 4 Parametern messbar); Aussage eingeschränkt.`
            : punkte >= 2
              ? `Ogata-Score ${punkte} von 4 Punkten -- vereinbar mit einem myelodysplastischen Syndrom. Der Score ersetzt weder Zytomorphologie noch Zytogenetik.`
              : `Ogata-Score ${punkte} von 4 Punkten -- kein durchflusszytometrischer Hinweis auf ein MDS. Ein MDS ist damit nicht ausgeschlossen (Sensitivität des Scores etwa 70 %).`,
      };
    },
  },

  /* ---------------------------------------------------------------- */
  egil: {
    id: 'egil',
    name: 'Linienzuordnung (WHO-Kriterien und EGIL-Score)',
    quelle: 'WHO-Klassifikation (MPAL-Kriterien); EGIL, Bene et al. 1995',
    berechne(ctx) {
      const z = 'blasten';
      const e = (m) => ctx.expression(z, m);
      const pos = (m, min = 2) => KLASSE_RANG[e(m).level] >= min;

      /* --- WHO-Linienkriterien (massgeblich) --- */
      const mpo = e('MPO');
      const cycd3 = e('cyCD3');
      const scd3 = e('CD3');
      const cd19 = e('CD19');
      const cd79a = e('CD79a');
      const cd10 = e('CD10');
      const cd22 = e('CD22');

      const myeloischWHO = KLASSE_RANG[mpo.level] >= 2;
      const monozytaer = ['CD11c', 'CD14', 'CD64'].filter((m) => pos(m)).length >= 2;
      const tWHO = KLASSE_RANG[cycd3.level] >= 3 || KLASSE_RANG[scd3.level] >= 2;
      const starkeBMarker = ['CD79a', 'CD22', 'CD10'].filter((m) => KLASSE_RANG[e(m).level] >= 3).length;
      const bWHO =
        (KLASSE_RANG[cd19.level] >= 3 && starkeBMarker >= 1) ||
        (KLASSE_RANG[cd19.level] >= 1 && starkeBMarker >= 2);

      const linienWHO = [];
      if (myeloischWHO || monozytaer) linienWHO.push('myeloisch');
      if (tWHO) linienWHO.push('T-Linie');
      if (bWHO) linienWHO.push('B-Linie');

      /* --- EGIL-Punktwerte (ergaenzend) --- */
      const egilB =
        (pos('CD79a') ? 2 : 0) + (pos('CD22') ? 2 : 0) + (pos('CD19') ? 1 : 0) + (pos('CD20') ? 1 : 0) +
        (pos('CD10') ? 1 : 0) + (pos('TdT') ? 0.5 : 0) + (pos('CD24') ? 0.5 : 0);
      const egilT =
        (KLASSE_RANG[cycd3.level] >= 2 || KLASSE_RANG[scd3.level] >= 2 ? 2 : 0) +
        (pos('CD2') ? 1 : 0) + (pos('CD5') ? 1 : 0) + (pos('CD8') ? 1 : 0) +
        (pos('CD7') ? 0.5 : 0) + (pos('CD1a') ? 0.5 : 0) + (pos('TdT') ? 0.5 : 0);
      const egilM =
        (pos('MPO') ? 2 : 0) + (pos('CD13') ? 1 : 0) + (pos('CD33') ? 1 : 0) + (pos('CD117') ? 1 : 0) +
        (pos('CD65') ? 1 : 0) + (pos('CD14') ? 0.5 : 0) + (pos('CD15') ? 0.5 : 0) + (pos('CD64') ? 0.5 : 0);

      const kriterien = [
        { name: 'MPO (myeloisch)', erfuellt: myeloischWHO, wert: mpo.level, gemessen: mpo.vorhanden },
        { name: 'Monozytäre Differenzierung (≥ 2 von CD11c/CD14/CD64)', erfuellt: monozytaer, wert: monozytaer ? 'ja' : 'nein', gemessen: true },
        { name: 'cyCD3 stark oder CD3 an der Oberfläche (T-Linie)', erfuellt: tWHO, wert: `cyCD3 ${cycd3.level}, CD3 ${scd3.level}`, gemessen: cycd3.vorhanden || scd3.vorhanden },
        { name: 'CD19 mit CD79a/CD22/CD10 (B-Linie)', erfuellt: bWHO, wert: `CD19 ${cd19.level}, CD79a ${cd79a.level}, CD22 ${cd22.level}, CD10 ${cd10.level}`, gemessen: cd19.vorhanden },
      ];

      let bewertung;
      let text;
      if (linienWHO.length === 0) {
        bewertung = 'nicht zuordenbar';
        text =
          'Keine der WHO-Linienkriterien erfüllt. Zu prüfen: akute undifferenzierte Leukämie, blastische plasmazytoide dendritische Zellneoplasie (CD123/CD4/CD56) oder eine nichthämatologische Neoplasie. Panel erweitern.';
      } else if (linienWHO.length === 1) {
        bewertung = linienWHO[0];
        text = `Die Blastenpopulation erfüllt die WHO-Kriterien der ${linienWHO[0]}. EGIL-Punktwerte: B ${egilB}, T ${egilT}, myeloisch ${egilM}.`;
      } else {
        bewertung = 'gemischter Phänotyp (MPAL)';
        text =
          `Die Blastenpopulation erfüllt die WHO-Linienkriterien für mehrere Linien (${linienWHO.join(' und ')}). ` +
          'Damit besteht der Verdacht auf eine akute Leukämie mit gemischtem Phänotyp (MPAL). Vor der endgültigen Einordnung ist zu prüfen, ob es sich um eine einzelne Population mit Koexpression oder um zwei getrennte Blastenpopulationen handelt. ' +
          `EGIL-Punktwerte: B ${egilB}, T ${egilT}, myeloisch ${egilM}.`;
      }

      return { punkte: linienWHO.length, maximum: 3, kriterien, bewertung, text, egil: { B: egilB, T: egilT, myeloisch: egilM }, linien: linienWHO };
    },
  },

  /* ---------------------------------------------------------------- */
  klonalitaet: {
    id: 'klonalitaet',
    name: 'B-Zell-Klonalität',
    quelle: 'Leichtkettenrestriktion, übliche Grenzwerte',
    berechne(ctx, metriken) {
      const quotient = metriken.find((m) => m.id === 'kl_ratio')?.wert;
      const bZellen = ctx.count(ctx.stepGates.bzell ? 'bzell' : 'lymph');
      const lkNegativ = metriken.find((m) => m.id === 'lk_negativ')?.wert;
      const grenzen = REFERENZBEREICHE.KAPPA_LAMBDA.klonalitaet;

      const ausreichend = bZellen >= 100;
      const klonal = Number.isFinite(quotient) && (quotient > grenzen.obereGrenze || quotient < grenzen.untereGrenze);
      const lkVerlust = Number.isFinite(lkNegativ) && lkNegativ > 25;

      const kriterien = [
        { name: `Kappa/Lambda-Quotient außerhalb ${grenzen.untereGrenze}–${grenzen.obereGrenze}`, erfuellt: klonal, wert: fmt(quotient, 2), gemessen: Number.isFinite(quotient) },
        { name: 'Mindestens 100 auswertbare B-Zellen', erfuellt: ausreichend, wert: `${bZellen}`, gemessen: true },
        { name: 'Leichtkettennegative B-Zellen ≤ 25 %', erfuellt: !lkVerlust, wert: fmt(lkNegativ, 1, ' %'), gemessen: Number.isFinite(lkNegativ) },
      ];

      let bewertung;
      let text;
      if (!ausreichend) {
        bewertung = 'nicht beurteilbar';
        text = `Nur ${bZellen} B-Zellen erfasst; für eine Klonalitätsaussage sind mindestens 100 B-Zellen erforderlich.`;
      } else if (klonal) {
        const dominanz = quotient > grenzen.obereGrenze ? 'Kappa' : 'Lambda';
        bewertung = 'klonale B-Zellpopulation';
        text = `Kappa/Lambda-Quotient ${fmt(quotient, 2)} -- Leichtkettenrestriktion zugunsten von ${dominanz}. Befund vereinbar mit einer klonalen B-Zellpopulation.`;
      } else if (lkVerlust) {
        bewertung = 'Leichtkettenverlust möglich';
        text = `${fmt(lkNegativ, 1)} % der B-Zellen zeigen keine nachweisbare Oberflächen-Leichtkette. Ein Leichtkettenverlust einer klonalen Population ist möglich; molekulare Klonalitätsanalyse empfohlen.`;
      } else {
        bewertung = 'polyklonal';
        text = `Kappa/Lambda-Quotient ${fmt(quotient, 2)} im polyklonalen Bereich. Kein Hinweis auf eine klonale B-Zellpopulation.`;
      }
      return { punkte: klonal ? 1 : 0, maximum: 1, kriterien, bewertung, text };
    },
  },

  /* ---------------------------------------------------------------- */
  pnh: {
    id: 'pnh',
    name: 'PNH-Klongröße',
    quelle: 'ICCS/ESCCA-Empfehlungen zur PNH-Diagnostik',
    berechne(ctx, metriken) {
      const gran = metriken.find((m) => m.id === 'gran_klon')?.wert;
      const mono = metriken.find((m) => m.id === 'mono_klon')?.wert;
      const ery = metriken.find((m) => m.id === 'ery_klon')?.wert;
      const nGran = ctx.count('granulo');
      const lod = metriken.find((m) => m.id === 'lod_gran')?.wert;

      const klon = Number.isFinite(gran) ? gran : mono;
      const kriterien = [
        { name: 'Granulozytenklon', erfuellt: gran > 0.01, wert: fmt(gran, 3, ' %'), gemessen: Number.isFinite(gran) },
        { name: 'Monozytenklon', erfuellt: mono > 0.01, wert: fmt(mono, 3, ' %'), gemessen: Number.isFinite(mono) },
        { name: 'Erythrozytenklon (Typ III)', erfuellt: ery > 0.01, wert: fmt(ery, 3, ' %'), gemessen: Number.isFinite(ery) },
        { name: '≥ 100 000 Granulozyten gemessen (hochsensitiv)', erfuellt: nGran >= 100000, wert: `${nGran}`, gemessen: true },
      ];

      let bewertung;
      let text;
      if (!Number.isFinite(klon)) {
        bewertung = 'nicht beurteilbar';
        text = 'PNH-Klon nicht bestimmbar; erforderliche Marker (FLAER, CD24, CD14/CD64) im Panel prüfen.';
      } else if (klon < (Number.isFinite(lod) ? lod : 0.01)) {
        bewertung = 'kein Klon nachweisbar';
        text = `Kein PNH-Klon oberhalb der Nachweisgrenze von ${fmt(lod, 3)} % nachweisbar.`;
      } else if (klon < 1) {
        bewertung = 'kleiner Klon';
        text = `Kleiner PNH-Klon: ${fmt(klon, 3)} % der Granulozyten. Klone unter 1 % sind ohne Hämolysezeichen in der Regel nicht therapiebedürftig; Verlaufskontrolle in 6-12 Monaten empfohlen.`;
      } else if (klon < 10) {
        bewertung = 'mittelgroßer Klon';
        text = `PNH-Klon ${fmt(klon, 2)} % der Granulozyten. Verlaufskontrolle und Korrelation mit LDH, Retikulozyten und Haptoglobin empfohlen.`;
      } else if (klon < 50) {
        bewertung = 'großer Klon';
        text = `Großer PNH-Klon: ${fmt(klon, 1)} % der Granulozyten. Bei Hämolysezeichen oder Thrombose ist eine hämatologische Vorstellung angezeigt.`;
      } else {
        bewertung = 'sehr großer Klon';
        text = `Sehr großer PNH-Klon: ${fmt(klon, 1)} % der Granulozyten. Klassische PNH wahrscheinlich; hämatologische Mitbetreuung erforderlich.`;
      }
      if (nGran < 100000 && Number.isFinite(klon)) {
        text += ` Hinweis: nur ${nGran.toLocaleString('de-DE')} Granulozyten gemessen; für die hochsensitive Analyse werden mindestens 100 000 gefordert.`;
      }
      return { punkte: Number.isFinite(klon) && klon > 0.01 ? 1 : 0, maximum: 1, kriterien, bewertung, text };
    },
  },

  /* ---------------------------------------------------------------- */
  euroclass: {
    id: 'euroclass',
    name: 'EUROclass-Einteilung',
    quelle: 'Wehr et al. 2008 (EUROclass)',
    berechne(ctx, metriken, sample, patient) {
      const alter = alterBestimmen(patient);
      const bPct = metriken.find((m) => m.id === 'b_pct')?.wert;
      const sm = metriken.find((m) => m.id === 'switched_pct')?.wert;
      const cd21 = metriken.find((m) => m.id === 'cd21low_pct')?.wert;
      const trans = metriken.find((m) => m.id === 'transitional_pct')?.wert;

      const bFehlend = Number.isFinite(bPct) && bPct < 1;
      const smNiedrig = Number.isFinite(sm) && sm < 2;
      const cd21Expandiert = Number.isFinite(cd21) && cd21 > 10;
      const transExpandiert = Number.isFinite(trans) && trans > 9;

      const teile = [];
      if (bFehlend) teile.push('B-');
      else {
        teile.push('B+');
        teile.push(smNiedrig ? 'smB-' : 'smB+');
        if (cd21Expandiert) teile.push('CD21low-Expansion');
        if (transExpandiert) teile.push('Trans-Expansion');
      }

      const kriterien = [
        { name: 'B-Zellen ≥ 1 % der Lymphozyten', erfuellt: !bFehlend, wert: fmt(bPct, 1, ' %'), gemessen: Number.isFinite(bPct) },
        { name: 'Geswitchte Gedächtnis-B-Zellen ≥ 2 % der B-Zellen', erfuellt: !smNiedrig, wert: fmt(sm, 1, ' %'), gemessen: Number.isFinite(sm) },
        { name: 'CD21-niedrige B-Zellen ≤ 10 %', erfuellt: !cd21Expandiert, wert: fmt(cd21, 1, ' %'), gemessen: Number.isFinite(cd21) },
        { name: 'Transitionale B-Zellen ≤ 9 %', erfuellt: !transExpandiert, wert: fmt(trans, 1, ' %'), gemessen: Number.isFinite(trans) },
      ];

      let text = `EUROclass-Muster: ${teile.join(' / ')}.`;
      if (bFehlend) text += ' Nahezu fehlende B-Zellen: Agammaglobulinämie (z. B. XLA) abklären.';
      else if (smNiedrig) text += ' Verminderte geswitchte Gedächtnis-B-Zellen sind bei CVID mit einem höheren Risiko für Granulome und Splenomegalie verbunden.';
      if (cd21Expandiert) text += ' Eine CD21-niedrige Expansion ist mit Splenomegalie und Autoimmunzytopenien assoziiert.';
      if (transExpandiert) text += ' Eine Expansion transitionaler B-Zellen ist mit Lymphadenopathie assoziiert.';
      if (Number.isFinite(alter) && alter < 6) text += ' Bei Kindern unter 6 Jahren sind altersabhängig niedrigere Gedächtnis-B-Zellwerte physiologisch.';

      return { punkte: kriterien.filter((k) => k.gemessen && !k.erfuellt).length, maximum: 4, kriterien, bewertung: teile.join('/'), text };
    },
  },

  /* ---------------------------------------------------------------- */
  mrd: {
    id: 'mrd',
    name: 'MRD-Quantifizierung',
    quelle: 'EuroFlow-Empfehlungen zu LOD und LLOQ',
    berechne(ctx, metriken) {
      const mrd = metriken.find((m) => m.id === 'mrd')?.wert;
      const lod = metriken.find((m) => m.id === 'lod')?.wert;
      const lloq = metriken.find((m) => m.id === 'lloq')?.wert;
      const events = metriken.find((m) => m.id === 'events')?.wert;
      const blasten = ctx.count('blasten');
      const ci = ctx.ci('blasten', 'leuko');

      const kriterien = [
        { name: '≥ 500 000 kernhaltige Zellen gemessen', erfuellt: events >= 500000, wert: Number.isFinite(events) ? events.toLocaleString('de-DE') : '–', gemessen: Number.isFinite(events) },
        { name: 'Clustergröße ≥ 20 Ereignisse (LOD)', erfuellt: blasten >= 20, wert: `${blasten}`, gemessen: true },
        { name: 'Clustergröße ≥ 50 Ereignisse (LLOQ)', erfuellt: blasten >= 50, wert: `${blasten}`, gemessen: true },
      ];

      let bewertung;
      let text;
      if (blasten < 20) {
        bewertung = 'MRD negativ';
        text = `Keine Population mit aberrantem Phänotyp oberhalb der Nachweisgrenze von ${fmt(lod, 4)} % nachweisbar (bei ${Number.isFinite(events) ? events.toLocaleString('de-DE') : '?'} ausgewerteten kernhaltigen Zellen).`;
      } else if (blasten < 50) {
        bewertung = 'MRD positiv, unterhalb der Bestimmungsgrenze';
        text = `Aberrante Population nachweisbar (${blasten} Ereignisse, ${fmt(mrd, 4)} %), jedoch unterhalb der Bestimmungsgrenze von ${fmt(lloq, 4)} %. Der Wert ist qualitativ positiv, aber nicht sicher quantifizierbar.`;
      } else {
        bewertung = 'MRD positiv';
        text = `MRD-Anteil ${fmt(mrd, 4)} % der kernhaltigen Zellen (${blasten} Ereignisse; 95-%-Vertrauensbereich ${fmt(ci.low, 4)}–${fmt(ci.high, 4)} %).`;
      }
      if (Number.isFinite(events) && events < 500000) {
        text += ` Einschränkung: nur ${events.toLocaleString('de-DE')} Zellen ausgewertet, angestrebt sind 500 000 für eine Sensitivität von 0,01 %.`;
      }
      return { punkte: blasten >= 20 ? 1 : 0, maximum: 1, kriterien, bewertung, text };
    },
  },

  /* ---------------------------------------------------------------- */
  tzell_aberranz: {
    id: 'tzell_aberranz',
    name: 'T-Zell-Aberranz',
    quelle: 'Uebliche Aberranzkriterien der T-Zell-Diagnostik',
    berechne(ctx, metriken, sample, patient) {
      const quotient = metriken.find((m) => m.id === 'cd4cd8')?.wert;
      const cd7 = metriken.find((m) => m.id === 'cd7neg_pct')?.wert;
      const cd26 = metriken.find((m) => m.id === 'cd26neg_pct')?.wert;
      const alter = alterBestimmen(patient);
      const refQuotient = bewerteReferenz('CD4_CD8_RATIO', quotient, alter);

      const kriterien = [
        { name: 'CD4/CD8-Quotient im Referenzbereich', erfuellt: refQuotient.status === 'normal', wert: fmt(quotient, 2), gemessen: Number.isFinite(quotient) },
        { name: 'CD7-Verlust ≤ 20 % der T-Zellen', erfuellt: !(cd7 > 20), wert: fmt(cd7, 1, ' %'), gemessen: Number.isFinite(cd7) },
        { name: 'CD26-Verlust ≤ 30 % der CD4+ T-Zellen', erfuellt: !(cd26 > 30), wert: fmt(cd26, 1, ' %'), gemessen: Number.isFinite(cd26) },
      ];
      const auffaellig = kriterien.filter((k) => k.gemessen && !k.erfuellt);

      let text;
      if (!auffaellig.length) {
        text = 'Regelhaftes T-Zell-Antigenmuster ohne Hinweis auf eine aberrante Population.';
      } else {
        text =
          `Auffällige Befunde: ${auffaellig.map((k) => `${k.name.replace(/ ≤.*| im Referenzbereich/, '')} (${k.wert})`).join(', ')}. ` +
          'Ein Antigenverlust ist ein Aberranzkriterium, aber nicht beweisend für Klonalität. Ergänzung durch Vbeta-Repertoire-Analyse oder molekulare TCR-Klonalitätsuntersuchung empfohlen.';
      }
      return { punkte: auffaellig.length, maximum: kriterien.length, kriterien, bewertung: auffaellig.length ? 'aberrant' : 'regelhaft', text };
    },
  },
};

function cd7Negativ(e) {
  return e.vorhanden && KLASSE_RANG[e.level] === 0;
}
function schwachOderNeg(e) {
  return e.vorhanden && KLASSE_RANG[e.level] <= 1;
}
function fmt(v, n = 1, suffix = '') {
  return Number.isFinite(v) ? v.toFixed(n).replace('.', ',') + suffix : '–';
}

/* ================================================================== */
/* Differentialdiagnose                                               */
/* ================================================================== */

/**
 * Vergleicht das gemessene Profil einer Population mit dem Entitaetskatalog.
 * @param {object} ctx Auswertungskontext
 * @param {string} step Schritt-ID der auffaelligen Population
 * @param {object} opts {gruppe} optionale Einschraenkung auf eine Entitaetsgruppe
 * @returns {Array} nach Passung sortierte Trefferliste
 */
export function differentialdiagnose(ctx, step, opts = {}) {
  const kandidaten = ENTITAETEN.filter((e) => !opts.gruppe || e.gruppe === opts.gruppe);
  const treffer = [];

  for (const ent of kandidaten) {
    const stuetzend = [];
    const widersprechend = [];
    const nichtGemessen = [];
    let gewichtSumme = 0;
    let punkte = 0;

    for (const marker of Object.keys(ent.profil)) {
      const echterName = marker.replace(/_/g, '-');
      const e = ctx.expression(step, echterName);
      const erw = erwartung(ent, marker);
      if (!e.vorhanden || !KLASSE_RANG[e.level] === undefined) {
        nichtGemessen.push(echterName);
        continue;
      }
      if (KLASSE_RANG[e.level] === undefined) {
        nichtGemessen.push(echterName);
        continue;
      }
      const istSchluessel = (ent.schluessel || []).includes(echterName);
      const gewicht = istSchluessel ? 2 : 1;
      const ok = passt(e.level, erw);
      if (ok === null) continue;
      gewichtSumme += gewicht;
      if (ok) {
        punkte += gewicht;
        if (erw !== '+/-') stuetzend.push(`${echterName} ${e.level}`);
      } else {
        widersprechend.push(`${echterName} ${e.level} (erwartet ${erw})`);
      }
    }

    if (gewichtSumme < 3) continue;
    treffer.push({
      entitaet: ent,
      passung: punkte / gewichtSumme,
      stuetzend,
      widersprechend,
      nichtGemessen,
      abdeckung: gewichtSumme,
    });
  }

  return treffer.sort((a, b) => b.passung - a.passung || b.abdeckung - a.abdeckung);
}

/* ================================================================== */
/* Gesamtbewertung                                                    */
/* ================================================================== */

/**
 * Vergleicht alle Kennzahlen mit den Referenzbereichen.
 * @returns {Array} Bewertungen inklusive Plausibilitaetspruefung
 */
export function bewerteMetriken(metriken, patient, katalog = REFERENZBEREICHE) {
  const alter = alterBestimmen(patient);
  return metriken.map((m) => {
    const bewertung = m.referenz ? bewerteReferenz(m.referenz, m.wert, alter, katalog) : { status: 'unbekannt', text: '' };
    let hinweis = null;
    if (m.plausibilitaet && Number.isFinite(m.wert)) {
      const [u, o] = m.plausibilitaet;
      if (m.wert < u || m.wert > o) {
        hinweis = `Plausibilitätsprüfung nicht bestanden (erwartet ${u}–${o}); Gating prüfen.`;
      }
    }
    if (m.schwellen && Number.isFinite(m.wert)) {
      if (Number.isFinite(m.schwellen.auffaellig) && m.wert >= m.schwellen.auffaellig) {
        hinweis = (hinweis ? hinweis + ' ' : '') + `Oberhalb der Auffälligkeitsschwelle von ${m.schwellen.auffaellig}.`;
      }
      if (Number.isFinite(m.schwellen.niedrig) && m.wert < m.schwellen.niedrig) {
        hinweis = (hinweis ? hinweis + ' ' : '') + `Unterhalb des erwarteten Mindestwerts von ${m.schwellen.niedrig}.`;
      }
    }
    // Absolutwerte gegen die passenden Referenzbereiche pruefen
    let absBewertung = null;
    if (Number.isFinite(m.absolut) && m.referenz) {
      const absSchluessel = m.referenz.replace('_LYMPH_PCT', '_ABS');
      if (katalog[absSchluessel]) absBewertung = bewerteReferenz(absSchluessel, m.absolut, alter, katalog);
    }
    return { ...m, bewertung, absBewertung, hinweis };
  });
}

/**
 * Fuehrt Kennzahlbewertung, Scores und Differentialdiagnose zusammen.
 * @returns {{metriken, scores, ddx, auffaelligkeiten, empfehlungen}}
 */
export function bewertePanel(sample, panel, ctx, metriken, patient, katalog = REFERENZBEREICHE) {
  const bewertet = bewerteMetriken(metriken, patient, katalog);

  const scores = [];
  for (const id of panel.scores || []) {
    const def = SCORES[id];
    if (!def) continue;
    try {
      scores.push({ id, name: def.name, quelle: def.quelle, ...def.berechne(ctx, metriken, sample, patient) });
    } catch (err) {
      scores.push({ id, name: def.name, quelle: def.quelle, bewertung: 'Fehler', text: `Score nicht berechenbar: ${err.message}`, kriterien: [] });
    }
  }

  // Differentialdiagnose fuer die vom Panel bezeichnete Zielpopulation
  const zielSchritt = ddxZielSchritt(panel, ctx);
  const ddx = zielSchritt ? differentialdiagnose(ctx, zielSchritt).slice(0, 5) : [];

  const auffaelligkeiten = [];
  for (const m of bewertet) {
    if (m.bewertung.status === 'erhoeht' || m.bewertung.status === 'erniedrigt') {
      auffaelligkeiten.push(`${m.name}: ${formatWert(m)} ${m.bewertung.text}`);
    }
    if (m.hinweis) auffaelligkeiten.push(`${m.name}: ${m.hinweis}`);
  }

  const empfehlungen = new Set();
  for (const s of scores) {
    if (s.bewertung === 'grenzwertig' || s.bewertung === 'nicht beurteilbar' || s.bewertung === 'unvollstaendig') {
      empfehlungen.add(`${s.name}: Panel erweitern, um die fehlenden Kriterien zu erfassen.`);
    }
  }
  if (ddx.length && ddx[0].nichtGemessen.length) {
    empfehlungen.add(
      `Zur Abgrenzung ${ddx[0].entitaet.kurz} gegen ${ddx[1]?.entitaet.kurz || 'die Differentialdiagnosen'} fehlen im Panel: ${ddx[0].nichtGemessen.slice(0, 6).join(', ')}.`,
    );
  }
  if (ddx.length && ddx[0].entitaet.dringend && ddx[0].passung > 0.75) {
    empfehlungen.add(`DRINGEND: ${ddx[0].entitaet.zusatz}`);
  }

  return { metriken: bewertet, scores, ddx, auffaelligkeiten, empfehlungen: [...empfehlungen] };
}

/** Waehlt die Population, auf die sich die Differentialdiagnose bezieht. */
function ddxZielSchritt(panel, ctx) {
  const kandidaten = {
    cll: 'cd5b',
    'klonalitaet-b': 'bzell',
    'akute-leukämie': 'blasten',
    'mrd-all': 'blasten',
    plasmazellen: 'pz_aberrant',
    'tzell-aberranz': 'tzell',
  };
  const gewuenscht = kandidaten[panel.id];
  if (gewuenscht && ctx.stepGates[gewuenscht]) return gewuenscht;
  return null;
}

export function formatWert(m) {
  if (!Number.isFinite(m.wert)) return '–';
  const s = m.wert.toFixed(m.nachkomma ?? 1).replace('.', ',');
  return m.einheit ? `${s} ${m.einheit}` : s;
}
