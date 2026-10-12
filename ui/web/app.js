


const STATUTS = {
  a_faire:  { classe: "afaire",  mot: "to do" },
  en_cours: { classe: "encours", mot: "in progress" },
  fait:     { classe: "fait",    mot: "done" },
  pret:     { classe: "pret",    mot: "ready" },
  clos:     { classe: "clos",    mot: "closed" },
  en_pause: { classe: "enpause", mot: "paused" },
};

const ORDRE_RESUME = ["pret", "en_cours", "a_faire", "en_pause", "fait", "clos"];


const CLOS_OU_FAIT = new Set(["fait", "clos"]);

let contrat = null;

let panier = null;

let vue = { genre: "intendant", clef: null };
let derniereVueRendue = "";



function echapper(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function enligne(s) {
  const codes = [];
  let out = echapper(s);

  out = out.replace(/`([^`]+)`/g, (_m, c) => `\uE000${codes.push(c) - 1}\uE001`);

  out = out.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_m, texte, cible) => `<span class="lien" title="${echapper(cible)}">${texte}</span>`
  );

  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  out = out.replaceAll("**", "").replaceAll("`", "");

  return out.replace(/\uE000(\d+)\uE001/g, (_m, i) => `<code>${echapper(codes[i])}</code>`);
}


function detailSansRedite(titre, detail) {
  if (!detail) return "";
  const tete = String(titre ?? "").replace(/[\u2026\s]+$/, "");
  if (tete.length > 24 && detail.startsWith(tete)) {
    return detail.slice(tete.length).replace(/^[\s\u2026]+/, "");
  }
  return detail;
}

function md(bloc) {
  const lignes = String(bloc ?? "").split("\n");
  const morceaux = [];
  let puces = null;
  let para = [];

  const viderPara = () => {
    if (para.length) morceaux.push(`<p>${para.join("<br>")}</p>`);
    para = [];
  };
  const viderPuces = () => {
    if (puces) morceaux.push(`<ul>${puces.join("")}</ul>`);
    puces = null;
  };

  for (const brute of lignes) {
    const ligne = brute.trim();
    const puce = ligne.match(/^[-*+]\s+(.*)$/);
    if (puce) {
      viderPara();
      (puces ??= []).push(`<li>${enligne(puce[1])}</li>`);
    } else if (!ligne) {
      viderPara();
      viderPuces();
    } else {
      viderPuces();
      para.push(enligne(ligne));
    }
  }
  viderPara();
  viderPuces();
  return morceaux.join("");
}



const el = (html) => {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
};

function depuis(iso) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 45) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

function etiquetteSensibilite(item) {
  const s = item.sensibilite;
  if (s !== "perso" && s !== "sensible") return "";
  return `<span class="etiquette ${s}">${s}</span>`;
}

function blocGeste(geste) {
  if (!geste) return "";
  return `<button class="geste" data-copier="${echapper(geste)}">${echapper(geste)}</button>`;
}




function nomCourt(chemin) {
  const s = String(chemin ?? "");
  return s.includes("/") ? s.slice(s.lastIndexOf("/") + 1) : s;
}


function blocLieu(item) {
  if (!item.fichier) return "";
  const ligne = item.ligne ? `<span class="lieu-ligne">line ${echapper(item.ligne)}</span>` : "";
  return `<div class="lieu-item" title="${echapper(item.fichier)}">` +
    `<span class="lieu-arc">${echapper(nomCourt(item.fichier))}</span>${ligne}</div>`;
}

function rendreItem(item, { statut = null } = {}) {
  const st = statut ? STATUTS[statut] : null;
  const classes = ["item", st ? st.classe : ""].filter(Boolean).join(" ");

  const clef = item.id ? `<span class="clef">${echapper(item.id)}</span>` : "";
  const badge = st ? `<span class="etiquette ${st.classe}">${item.libelle || st.mot}</span>` : "";
  const texte = detailSansRedite(item.titre, item.detail);
  const detail = texte ? `<div class="detail">${md(texte)}</div>` : "";
  const chemin = item.chemin ? `<div class="chemin-item">${echapper(item.chemin)}</div>` : "";

  return el(`
    <article class="${classes}">
      <div class="glyphe"><span class="marque-statut"></span></div>
      <div class="item-corps">
        <div class="item-tete">
          ${clef}
          <span class="item-titre">${enligne(item.titre)}</span>
          ${badge}
          ${etiquetteSensibilite(item)}
        </div>
        ${detail}
        ${chemin}
        ${blocGeste(item.geste)}
        ${blocLieu(item)}
      </div>
    </article>
  `);
}



function rendrePlan(plan, sur) {
  const scene = document.createElement("div");
  scene.className = "scene-large";

  const etat = plan.etat;
  const arcs = plan.arcs ?? [];
  scene.append(el(`
    <header class="tete-vue">
      <div class="tete-sur">${echapper(sur)}</div>
      <h1 class="tete-titre">${echapper(plan.titre || plan.nom || "Mnémosyne")}</h1>
      ${plan.cap ? `<div class="tete-cap"><b>Cap</b> - ${enligne(plan.cap)}</div>` : ""}
      ${plan.chemin
        ? `<div class="tete-chemin"><span class="jeton-porte">porte</span>${echapper(plan.chemin)}</div>`
        : ""}
    </header>
  `));

  if (etat === "absent") {
    scene.append(el(`
      <div class="etat-bloc absent">
        <div class="etat-titre">This project has no plan yet</div>
        <div class="etat-texte">
          No <code>PLAN.md</code> exists at this location - nothing was ever written,
          this is not a plan that became empty. A session of that project will lay it down:
          <code>make plans</code> hands over the skeleton to paste.
        </div>
        ${plan.pourquoi ? `<div class="etat-pourquoi">${echapper(plan.pourquoi)}</div>` : ""}
      </div>
    `));
    return scene;
  }

  if (etat === "illisible" || etat === "indisponible") {
    scene.append(el(`
      <div class="etat-bloc indisponible">
        <div class="etat-titre">I could not read this plan</div>
        <div class="etat-texte">
          The file exists but nothing could be drawn from it. This is not an empty project -
          it is a project I know nothing about.
        </div>
        ${plan.pourquoi ? `<div class="etat-pourquoi">${echapper(plan.pourquoi)}</div>` : ""}
      </div>
    `));
    return scene;
  }

  const items = plan.items ?? [];


  const parFichier = new Map();
  for (const it of items) {
    const f = it.fichier || plan.chemin || "";
    if (!parFichier.has(f)) parFichier.set(f, []);
    parFichier.get(f).push(it);
  }


  const ordre = [];
  const vus = new Set();
  const pousser = (f) => {
    if (f && !vus.has(f)) { vus.add(f); ordre.push(f); }
  };
  pousser(plan.chemin);
  for (const a of arcs) pousser(a);
  for (const f of parFichier.keys()) pousser(f);

  const parStatut = {};
  for (const it of items) (parStatut[it.etat] ??= []).push(it);

  const resume = el(`<div class="resume"></div>`);
  for (const clef of ORDRE_RESUME) {
    const lot = parStatut[clef];
    if (!lot?.length) continue;
    resume.append(el(
      `<span class="puce-resume ${STATUTS[clef].classe}"><span class="n">${lot.length}</span>` +
      `<span class="l">${STATUTS[clef].mot}</span></span>`
    ));
  }
  if (resume.children.length) scene.append(resume);


  const groupes = [];
  for (const fichier of ordre) {
    const lot = parFichier.get(fichier) ?? [];
    const bloc = el(`<section class="arc"></section>`);

    if (arcs.length) {
      const role = fichier === plan.chemin ? "porte" : "arc";
      bloc.append(el(`
        <h2 class="arc-tete">
          <span class="jeton-${role}">${role}</span>
          <span class="arc-nom">${echapper(nomCourt(fichier))}</span>
          <span class="arc-chemin">${echapper(fichier)}</span>
        </h2>
      `));
      if (!lot.length) {
        bloc.append(el(`<div class="arc-vide">No item - this file carries prose only.</div>`));
      }
    }

    const sections = new Map();
    for (const it of lot) {
      const nom = it.section || "";
      if (!sections.has(nom)) sections.set(nom, []);
      sections.get(nom).push(it);
    }
    for (const [nom, sousLot] of sections) {
      const sec = el(`<section class="section"></section>`);
      if (nom) sec.append(el(`<h3 class="section-titre">${enligne(nom)}</h3>`));
      const liste = el(`<div class="liste"></div>`);
      for (const it of sousLot) liste.append(rendreItem(it, { statut: it.etat }));
      sec.append(liste);
      bloc.append(sec);
    }

    groupes.push({ fichier, lot, bloc });
  }

  if (arcs.length) {
    const index = el(`
      <div class="index-arcs">
        <div class="index-tete">This plan is a <b>folder</b>: a door, and its arcs.
          Each item below says <b>which arc</b> it lives in.</div>
        <div class="index-puces"></div>
      </div>
    `);
    const puces = index.querySelector(".index-puces");
    for (const g of groupes) {
      const puce = el(`
        <button class="puce-arc${g.lot.length ? "" : " muet"}" title="${echapper(g.fichier)}">
          <span class="puce-arc-nom">${echapper(nomCourt(g.fichier))}</span>
          <span class="puce-arc-n">${g.lot.length || "-"}</span>
        </button>
      `);
      puce.addEventListener("click", () => g.bloc.scrollIntoView({ behavior: "smooth", block: "start" }));
      puces.append(puce);
    }
    scene.append(index);
  }

  if (!items.length) {
    scene.append(el(`<div class="vide">This plan is readable, and it contains no item.</div>`));
  }
  for (const g of groupes) scene.append(g.bloc);

  const refus = plan.refus ?? [];
  if (refus.length) {
    const bloc = el(`
      <div class="refus">
        <b>${refus.length} line${refus.length > 1 ? "s" : ""} of the plan could not be read</b>
        - their status does not parse, so they are not displayed above.
        <ul></ul>
      </div>
    `);
    const ul = bloc.querySelector("ul");
    for (const r of refus) {
      const ou = r.fichier
        ? `<code>${echapper(r.fichier)}</code> <code>line ${echapper(r.ligne)}</code>`
        : `<code>line ${echapper(r.ligne)}</code>`;
      ul.append(el(
        `<li>${ou}  -  ${echapper(r.genre)}` +
        `${r.detail ? ` - ${echapper(r.detail)}` : ""}</li>`
      ));
    }
    scene.append(bloc);
  }

  const prose = plan.prose ?? {};
  if (prose.lignes_total) {
    const lues = prose.lignes_total - prose.lignes_prose;
    const ou = arcs.length ? "this plan (the door and its arcs)" : "this plan";
    scene.append(el(`
      <div class="note-bas">
        Out of <b>${prose.lignes_total}</b> lines of ${ou}, <b>${prose.lignes_prose}</b> are
        prose the reader does not display - the reasoning lives there, and that is normal.
        The other <b>${lues}</b> are what it read: the item lines and their indented detail.
        ${prose.sans_identite
          ? ` <b>${prose.sans_identite}</b> item(s) have no identity (checkbox notation):
             displayable, but impossible to follow from one edit to the next.`
          : ""}
        ${prose.tableaux_de_synthese?.length
          ? ` WARNING: ${prose.tableaux_de_synthese.length} table(s) contain status glyphs:
             a possible second source, flagged without being refused.` +
            (arcs.length
              ? ` The contract gives their line numbers (${prose.tableaux_de_synthese.join(", ")})
                 <b>without saying in which file</b> - on a folder-plan, those numbers locate
                 nothing, and I prefer to say so rather than send you looking in the wrong place.`
              : ` Lines ${prose.tableaux_de_synthese.join(", ")}.`)
          : ""}
      </div>
    `));
  }

  return scene;
}



function rendreFile(file) {
  const scene = document.createElement("div");
  scene.className = "scene-large";

  scene.append(el(`
    <header class="tete-vue">
      <div class="tete-sur">Mnémosyne queue</div>
      <h1 class="tete-titre">${enligne(file.titre)}</h1>
      ${file.source ? `<div class="tete-chemin">${echapper(file.source)}</div>` : ""}
    </header>
  `));

  if (file.etat === "absente") {
    scene.append(el(`
      <div class="etat-bloc absent">
        <div class="etat-titre">Never used</div>
        <div class="etat-texte">
          The storage for this queue does not exist: nothing was ever placed in it.
          This is not a queue that was emptied.
        </div>
        ${file.pourquoi ? `<div class="etat-pourquoi">${echapper(file.pourquoi)}</div>` : ""}
      </div>
    `));
    return scene;
  }

  if (file.etat === "indisponible") {
    scene.append(el(`
      <div class="etat-bloc indisponible">
        <div class="etat-titre">I could not read this queue</div>
        <div class="etat-texte">
          It exists, and reading it failed. The number of items in it is <b>unknown</b> -
          certainly not zero. The other queues remain read.
        </div>
        ${file.pourquoi ? `<div class="etat-pourquoi">${echapper(file.pourquoi)}</div>` : ""}
      </div>
    `));
    return scene;
  }

  const items = file.items ?? [];

  if (file.pourquoi) {
    scene.append(el(`
      <div class="etat-bloc">
        <div class="etat-titre">Read, with a reservation</div>
        <div class="etat-pourquoi">${echapper(file.pourquoi)}</div>
      </div>
    `));
  }

  if (!items.length) {
    scene.append(el(`<div class="vide">Nothing pending. This queue was indeed read: it is empty.</div>`));
  } else {

    if (file.clef === "runs_parques") {
      scene.append(el(`
        <div class="note-arc">
          Each run carries its key qualified by its <b>plan</b>, and the path of the
          <b>member file</b> - the arc where the line really lives.
        </div>
      `));
    }
    const liste = el(`<div class="liste"></div>`);
    for (const it of items) liste.append(rendreItem(it, { statut: it.etat === "pret" ? "pret" : null }));
    scene.append(liste);
  }

  if (file.geste) {
    scene.append(el(`
      <div class="note-bas">
        To open this queue in your terminal: ${blocGeste(file.geste)}
      </div>
    `));
  }

  return scene;
}



const AGENT_CLEF = "mnemosyne-ui/agent-choisi";


const LARGEUR_PANNEAU_CLEF = "mnemosyne-ui/panneau-largeur";
const LARGEUR_PANNEAU_DEFAUT = 360;

function lireLargeurPanneau() {
  const v = parseInt(localStorage.getItem(LARGEUR_PANNEAU_CLEF), 10);
  return Number.isFinite(v) ? v : LARGEUR_PANNEAU_DEFAUT;
}

let largeurPanneau = lireLargeurPanneau();

function agentChoisi() {
  try { return localStorage.getItem(AGENT_CLEF) || ""; } catch { return ""; }
}

function choisirAgent(id) {
  try { localStorage.setItem(AGENT_CLEF, id); } catch {  }
}


function nomAgent(id) {
  const s = String(id ?? "");
  return s.includes("/") ? s.slice(s.lastIndexOf("/") + 1) : s;
}

const GO = 1024 ** 3;
const enGo = (octets) => (octets / GO).toFixed(2).replace(".", ",");


let fil = [];
let enAttente = false;

let brouillonDiscussion = "";

let atelier = { vivant: false, modele: "", tours: 0 };

async function lireAtelier() {
  try {
    atelier = await (await fetch("/api/atelier", { cache: "no-store" })).json();
  } catch {
    atelier = { vivant: false, modele: "", tours: 0 };
  }
}




const RAYON = 9;
const PERIMETRE = 2 * Math.PI * RAYON;


const SEUIL_REPLI = 600;


let dernierFilRendu = -1;
let dernierEnAttenteRendu = false;

function anneauContexte() {
  const { jetons = 0, fenetre = 0 } = atelier;
  if (!fenetre || !jetons) return "";
  const part = Math.min(1, jetons / fenetre);
  return `
    <button class="anneau" title="Context window - click for the detail">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle class="anneau-fond" cx="12" cy="12" r="${RAYON}"></circle>
        <circle class="anneau-part" cx="12" cy="12" r="${RAYON}"
                stroke-dasharray="${(part * PERIMETRE).toFixed(2)} ${PERIMETRE.toFixed(2)}"></circle>
      </svg>
      <span class="anneau-pc">${(part * 100).toFixed(part < 0.1 ? 1 : 0)} %</span>
    </button>`;
}


function brancherAnneau(barre, { onCompacter } = {}) {
  const bouton = barre.querySelector(".anneau");
  if (!bouton) return;
  bouton.addEventListener("click", () => {
    const ouverte = barre.querySelector(".bulle-contexte");
    if (ouverte) { ouverte.remove(); return; }
    const { jetons = 0, fenetre = 0, fenetre_source: source = "", jetons_invite: inv, jetons_reponse: rep } = atelier;
    const bulle = el(`
      <div class="bulle-contexte">
        <div class="bulle-titre">Context window</div>
        <div class="bulle-gros">${jetons.toLocaleString("fr-FR")}
          <small>/ ${fenetre.toLocaleString("fr-FR")} tokens</small></div>
        ${inv != null && rep != null
          ? `<div class="bulle-ligne">Last turn: <b>${inv.toLocaleString("fr-FR")}</b> tokens sent
             (the thread included) and <b>${rep.toLocaleString("fr-FR")}</b> received.</div>`
          : ""}
        ${atelier.fil_total != null
          ? `<div class="bulle-ligne">Thread sent at the last turn:
             <b>${atelier.fil_garde}</b> exchange(s) out of ${atelier.fil_total}${
               atelier.fil_garde < atelier.fil_total
                 ? ` - the oldest ones were dropped, for lack of room.`
                 : ` - <b>nothing was left aside</b>.`
             }</div>`
          : ""}
        <div class="bulle-ligne">The bound is not a number of messages: it is the engine's
          input ceiling${
            atelier.plafond_caracteres
              ? `, <b>${atelier.plafond_caracteres.toLocaleString("fr-FR")} characters</b>`
              : ""
          }. The thread fills from the most recent towards the oldest and stops when it no longer
          fits - the engine <b>refuses</b> an oversized prompt instead of truncating it silently.</div>
        <div class="bulle-source">Size read from the model's <code>config.json</code>,
          field <code>${echapper(source || "?")}</code> - this is what the model
          <b>declares</b>, not a measurement of what it handles well.</div>
        ${onCompacter ? `
          <button class="bouton-compacter">Compact</button>
          <div class="bulle-note">Empties the displayed conversation - what concerns you (portrait,
            reminders) stays, nothing is deleted on disk.</div>
        ` : ""}
      </div>
    `);
    bulle.querySelector(".bouton-compacter")?.addEventListener("click", async () => {
      await onCompacter();
    });
    barre.append(bulle);
  });
}

function rendreDiscussion() {
  const scene = document.createElement("div");
  scene.className = "scene-large";

  scene.append(el(`
    <header class="tete-vue">
      <div class="tete-sur">Mnémosyne</div>
      <h1 class="tete-titre">Discussion</h1>
      <div class="tete-cap">Talk to a model running <b>on this Mac</b> - nothing leaves here.</div>
    </header>
  `));


  if (!panier || panier._lecture?.ok !== true) {
    scene.append(el(`
      <div class="etat-bloc indisponible">
        <div class="etat-titre">${echapper(panier?._lecture?.titre || "I could not read the model basket.")}</div>
        <div class="etat-texte">
          The number of available models is <b>unknown</b> - certainly not zero.
          In a terminal, <code>make modeles</code> says what Mnémosyne thinks of it.
        </div>
        ${panier?._lecture?.detail ? `<div class="etat-pourquoi">${echapper(panier._lecture.detail)}</div>` : ""}
      </div>
    `));
    return scene;
  }

  const modeles = (panier.modeles ?? []).filter((m) => m.utilisable !== false);
  const ram = panier.ram_octets || 0;
  const choisi = modeles.find((m) => m.id === agentChoisi()) ?? null;

  scene.append(el(`
    <div class="note-arc">
      The model runs locally and decoding goes through the Guard. The first message may
      take longer while the worker starts up; delays depend on the chosen model.
      <br>This screen does not keep the discussion thread after a reload.
    </div>
  `));

  const bloc = el(`
    <section class="agents">
      <h2 class="agents-tete">
        <span class="agents-titre">The agent</span>
        <span class="agents-sous">${modeles.length} models available locally</span>
      </h2>
      <div class="agents-grille"></div>
    </section>
  `);
  const grille = bloc.querySelector(".agents-grille");

  for (const m of modeles) {
    const part = ram ? (100 * m.octets) / ram : 0;

    const carte = el(`
      <button class="agent${m.id === choisi?.id ? " actif" : ""}${m.utilisable ? "" : " indispo"}"
              title="${echapper(m.id)}" ${m.utilisable ? "" : "disabled"}>
        <span class="agent-nom">${echapper(nomAgent(m.id))}</span>
        <span class="agent-chiffres">
          <span class="agent-go">${enGo(m.octets)} <small>GB</small></span>
          <span class="agent-part">${part.toFixed(0)} %</span>
        </span>
        <span class="agent-jauge"><i style="width:${Math.min(100, part).toFixed(1)}%"></i></span>
        ${m.utilisable ? "" : `<span class="agent-avert">declared, but incomplete on disk</span>`}
      </button>
    `);
    carte.addEventListener("click", () => {
      if (m.id === choisi?.id) return;
      choisirAgent(m.id);
      fil = [];
      dessiner();
    });
    grille.append(carte);
  }
  scene.append(bloc);

  const charge = modeles.find((m) => m.id === atelier.modele) ?? null;
  const barre = el(`
    <div class="atelier${atelier.vivant ? " vif" : ""}">
      <span class="atelier-point"></span>
      <span class="atelier-dit">${
        atelier.vivant
          ? `<b>${echapper(nomAgent(atelier.modele))}</b> is loaded in memory${
              charge ? ` - ${enGo(charge.octets)} GB` : ""
            }${atelier.tours ? `  -  ${atelier.tours} turn(s)` : ""}`
          : `No agent loaded - memory is free.`
      }</span>
      ${atelier.vivant ? anneauContexte() : ""}
      ${atelier.vivant ? `<button class="arreter">Stop</button>` : ""}
    </div>
  `);
  brancherAnneau(barre);
  barre.querySelector(".arreter")?.addEventListener("click", async (ev) => {
    const bouton = ev.currentTarget;
    bouton.disabled = true;
    bouton.textContent = "stopping...";
    try {
      await fetch("/api/arreter", { method: "POST" });
    } catch {  }
    fil = [];
    await lireAtelier();
    dessiner();
  });
  scene.append(barre);

  const scrollAvant = document.querySelector(".fil")?.scrollTop ?? 0;
  const bloc_fil = el(`<section class="fil"></section>`);
  if (!fil.length && !enAttente) {
    bloc_fil.append(el(`
      <div class="fil-vide">
        ${choisi
          ? `No message. The chosen agent is <code>${echapper(choisi.id)}</code>.`
          : `Choose an agent above to start.`}
      </div>
    `));
  }
  for (const tour of fil) {
    if (tour.qui === "refus") {
      bloc_fil.append(el(`
        <div class="tour refus-tour">
          <div class="tour-qui">refusal - ${echapper(tour.genre || "")}</div>
          <pre class="tour-detail">${echapper(tour.texte)}</pre>
        </div>
      `));
      continue;
    }


    const long = tour.qui === "operator" && tour.texte.length > SEUIL_REPLI && !tour.deplie;
    const bulleTour = el(`
      <div class="tour ${tour.qui === "operator" ? "de-operator" : "de-agent"}">
        <div class="tour-qui">${tour.qui === "operator" ? "You" : echapper(nomAgent(tour.modele || ""))}${
          tour.secondes != null ? `  -  ${tour.secondes}s` : ""
        }</div>
        <div class="tour-texte${long ? " coupe" : ""}">${echapper(tour.texte).replaceAll("\n", "<br>")}</div>
        ${long
          ? `<button class="voir-tout">See all - ${tour.texte.length.toLocaleString("fr-FR")} characters</button>`
          : ""}
      </div>
    `);
    bulleTour.querySelector(".voir-tout")?.addEventListener("click", () => {
      tour.deplie = true;
      dessiner();
    });
    bloc_fil.append(bulleTour);
  }
  if (enAttente) {
    bloc_fil.append(el(`
      <div class="tour de-agent attente-tour">
        <div class="tour-qui">${echapper(nomAgent(choisi?.id || ""))}</div>
        <div class="tour-texte"><span class="chrono" id="chrono">0,0 s</span> - thinking...</div>
      </div>
    `));
  }

  const cadre = el(`<div class="fil-cadre"></div>`);
  const bas = el(`<button class="vers-le-bas" hidden>down Last message</button>`);
  bas.addEventListener("click", () => {
    bloc_fil.scrollTo({ top: bloc_fil.scrollHeight, behavior: "smooth" });
  });
  const jauger = () => {
    const reste = bloc_fil.scrollHeight - bloc_fil.scrollTop - bloc_fil.clientHeight;
    bas.hidden = reste < 24;
  };
  bloc_fil.addEventListener("scroll", jauger);
  cadre.append(bloc_fil, bas);
  scene.append(cadre);

  const nouveaute = fil.length !== dernierFilRendu || (enAttente && !dernierEnAttenteRendu);
  dernierFilRendu = fil.length;
  dernierEnAttenteRendu = enAttente;
  setTimeout(() => {
    bloc_fil.scrollTop = nouveaute ? bloc_fil.scrollHeight : scrollAvant;
    jauger();
  }, 0);

  const composeur = el(`
    <div class="composeur">
      <textarea rows="2" ${choisi && !enAttente ? "" : "disabled"} placeholder="${
        !choisi ? "Choose an agent first." : enAttente ? "..." : "Write, then Enter."
      }">${echapper(brouillonDiscussion)}</textarea>
      <button class="envoyer" ${choisi && !enAttente ? "" : "disabled"}>Envoyer</button>
    </div>
  `);
  const zone = composeur.querySelector("textarea");
  zone.addEventListener("input", () => { brouillonDiscussion = zone.value; });
  const envoyer = async () => {
    const texte = zone.value.trim();
    if (!texte || !choisi || enAttente) return;
    brouillonDiscussion = "";
    fil.push({ qui: "operator", texte });
    enAttente = true;
    dessiner();
    const depart = Date.now();
    const tic = setInterval(() => {
      const c = document.getElementById("chrono");
      if (c) c.textContent = `${((Date.now() - depart) / 1000).toFixed(1).replace(".", ",")} s`;
    }, 100);
    try {
      const rep = await fetch("/api/dire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modele: choisi.id, texte }),
      });
      const dit = await rep.json();
      if (dit.etat === "reponse") {
        fil.push({ qui: "agent", texte: dit.texte, modele: dit.modele, secondes: dit.secondes });
        atelier = {
          ...atelier,
          jetons_invite: dit.jetons_invite,
          jetons_reponse: dit.jetons_reponse,
          fil_garde: dit.fil_garde,
          fil_total: dit.fil_total,
          plafond_caracteres: dit.plafond_caracteres,
        };
      } else {
        fil.push({ qui: "refus", genre: dit.genre, texte: dit.detail || "" });
      }
    } catch (err) {
      fil.push({ qui: "refus", genre: "serveur_injoignable", texte: String(err) });
    } finally {
      clearInterval(tic);
      enAttente = false;
      await lireAtelier();
      dessiner();
    }
  };
  composeur.querySelector(".envoyer").addEventListener("click", envoyer);
  zone.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      envoyer();
    }
  });
  scene.append(composeur);
  if (choisi && !enAttente) setTimeout(() => zone.focus(), 0);

  const dehors = panier.hors_panier ?? [];
  const refus = panier.refus ?? [];
  if (refus.length) {
    const b = el(`<div class="refus"><b>${refus.length} refusal(s) on the basket</b><ul></ul></div>`);
    const ul = b.querySelector("ul");
    for (const r of refus) {
      ul.append(el(`<li><code>${echapper(r.genre)}</code> - ${echapper(r.phrase || "")} <code>${echapper(r.detail)}</code></li>`));
    }
    scene.append(b);
  }
  scene.append(el(`
    <div class="note-bas">
      Basket declared in <code>${echapper(panier.panier || "")}</code>, measured on
      ${echapper(panier.mesure_le || "?")}, and checked against the disk
      <b>in both directions</b> in <b>${echapper(panier.verifie_ms)} ms</b> just now.
      ${dehors.length
        ? ` ${dehors.length} cache repo(s) are <b>outside the basket</b> - search and OCR
           bricks, not brains: ${dehors.map((d) => `<code>${echapper(d)}</code>`).join(", ")}.
           They are named rather than filtered out silently.`
        : ""}
    </div>
  `));

  return scene;
}






const FIL_CLEF = "mnemosyne-ui/intendant-fil";

const FIL_CONSEILLER_CLEF = "mnemosyne-ui/conseiller-fil";


let intendant = null;
let filIntendant = null;
let enAttenteIntendant = false;
let dernierFilIntendantRendu = -1;
let dernierEnAttenteIntendantRendu = false;

let ressorti = { rappels: [], connexes: [] };

let enVol = "";

let brouillonIntendant = "";

let messagesEnAttente = [];

async function api(corps) {
  const rep = await fetch("/api/intendant", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  return rep.json();
}


async function lireIntendant({ filDemande = null } = {}) {
  try {
    intendant = await (await fetch("/api/intendant", { cache: "no-store" })).json();
  } catch (err) {
    intendant = { etat: "refus", genre: "serveur_injoignable", detail: String(err) };
    return;
  }
  const vise = filDemande ?? localStorage.getItem(FIL_CLEF) ?? "";
  const rep = await api({ geste: "fil", id: vise });
  filIntendant = rep.fil ?? null;

  if (!filIntendant && vise) {
    localStorage.removeItem(FIL_CLEF);
    filIntendant = (await api({ geste: "fil", id: "" })).fil ?? null;
  }
  if (filIntendant) localStorage.setItem(FIL_CLEF, filIntendant.id);
}


let conseiller = null;
let filConseiller = null;
let enAttenteConseiller = false;
let dernierFilConseillerRendu = -1;
let dernierEnAttenteConseillerRendu = false;

let ressortiConseiller = { proches: [], connexes: [] };
let enVolConseiller = "";
let brouillonConseiller = "";
let messagesEnAttenteConseiller = [];

async function apiConseiller(corps) {
  const rep = await fetch("/api/conseiller", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  return rep.json();
}

async function lireConseiller({ filDemande = null } = {}) {
  try {
    conseiller = await (await fetch("/api/conseiller", { cache: "no-store" })).json();
  } catch (err) {
    conseiller = { etat: "refus", genre: "serveur_injoignable", detail: String(err) };
    return;
  }
  const vise = filDemande ?? localStorage.getItem(FIL_CONSEILLER_CLEF) ?? "";
  const rep = await apiConseiller({ geste: "fil", id: vise });
  filConseiller = rep.fil ?? null;
  if (!filConseiller && vise) {
    localStorage.removeItem(FIL_CONSEILLER_CLEF);
    filConseiller = (await apiConseiller({ geste: "fil", id: "" })).fil ?? null;
  }
  if (filConseiller) localStorage.setItem(FIL_CONSEILLER_CLEF, filConseiller.id);
}


function brancherRedimensionneur(poignee, scene) {
  let actif = false;

  const bouger = (ev) => {
    if (!actif) return;
    const rect = scene.getBoundingClientRect();
    const max = Math.max(240, rect.width - 280 - 14);
    largeurPanneau = Math.min(max, Math.max(240, rect.right - ev.clientX));
    scene.style.setProperty("--panneau-largeur", `${largeurPanneau}px`);
  };
  const relacher = () => {
    if (!actif) return;
    actif = false;
    poignee.classList.remove("actif");
    document.removeEventListener("mousemove", bouger);
    document.removeEventListener("mouseup", relacher);
    document.body.style.userSelect = "";
    try { localStorage.setItem(LARGEUR_PANNEAU_CLEF, String(Math.round(largeurPanneau))); } catch {

    }
  };
  poignee.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    actif = true;
    poignee.classList.add("actif");
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", bouger);
    document.addEventListener("mouseup", relacher);
  });
}

function rendreIntendant() {

  const scene = document.createElement("div");
  scene.className = "scene-intendant-liste";
  scene.style.setProperty("--panneau-largeur", `${largeurPanneau}px`);
  const chat = document.createElement("div");
  chat.className = "colonne-chat";
  const redimensionneur = el(`<div class="redimensionneur" title="Drag to resize"></div>`);
  brancherRedimensionneur(redimensionneur, scene);
  scene.append(chat, redimensionneur, rendreListePanneau());

  chat.append(el(`
    <header class="tete-vue tete-vue-compacte">
      <div class="tete-ligne">Mnémosyne <span aria-hidden="true">-</span> <b>The Steward</b></div>
    </header>
  `));

  if (!intendant || intendant.etat !== "ok") {
    chat.append(el(`
      <div class="panne">
        <h2>The Steward's store did not answer.</h2>
        <div>Nothing is displayed below: I prefer to show nothing rather than an
          empty store, which would read " you have noted nothing ".</div>
        <pre>${echapper(intendant?.detail || intendant?.genre || "unexpected response")}</pre>
      </div>
    `));
    return scene;
  }

  const choisi = (panier?.modeles ?? []).find((m) => m.id === agentChoisi()) || null;




  const scrollAvant = document.querySelector(".fil")?.scrollTop ?? 0;

  const zoneAvant = document.querySelector(".composeur-intendant textarea");
  const avaitFocus = zoneAvant != null && document.activeElement === zoneAvant;
  const selectionAvant = avaitFocus ? [zoneAvant.selectionStart, zoneAvant.selectionEnd] : null;
  const bloc = el(`<section class="fil"></section>`);
  const tours = filIntendant?.tours ?? [];
  if (!tours.length && !enAttenteIntendant) {
    bloc.append(el(`
      <div class="fil-vide">
        ${filIntendant
          ? `Empty thread. Tell it anything - it will file it away.`
          : `No thread yet. Write below: it will open one.`}
      </div>
    `));
  }
  for (const tour of tours) {
    const deOperator = tour.role === "operator";

    const long = deOperator && tour.texte.length > SEUIL_REPLI && !tour.deplie;
    const b = el(`
      <div class="tour ${deOperator ? "de-operator" : "de-agent"}">
        <div class="tour-qui">${deOperator ? "You" : "The Steward"}${
          tour.secondes != null ? `  -  ${tour.secondes}s` : ""
        }</div>
        <div class="tour-texte${long ? " coupe" : ""}">${echapper(tour.texte).replaceAll("\n", "<br>")}</div>
        ${long ? `<button class="voir-tout">See all - ${tour.texte.length.toLocaleString("fr-FR")} characters</button>` : ""}
      </div>
    `);
    b.querySelector(".voir-tout")?.addEventListener("click", () => { tour.deplie = true; dessiner(); });
    bloc.append(b);
  }
  if (enVol) {
    bloc.append(el(`
      <div class="tour de-operator en-vol">
        <div class="tour-qui">You</div>
        <div class="tour-texte">${echapper(enVol).replaceAll("\n", "<br>")}</div>
      </div>
    `));
  }
  if (enAttenteIntendant) {
    bloc.append(el(`
      <div class="tour de-agent attente-tour">
        <div class="tour-qui">The Steward</div>
        <div class="tour-texte"><span class="chrono" id="chrono-i">0,0 s</span> - thinking...</div>
      </div>
    `));
  }

  if (ressorti.rappels.length || ressorti.connexes.length) {
    const b = el(`<div class="ressorti"></div>`);
    for (const r of ressorti.rappels) {
      b.append(el(`<div class="ressorti-ligne rappel"><- set aside for this moment - ${echapper(r.texte)}</div>`));
    }
    for (const c of ressorti.connexes) {
      b.append(el(`<div class="ressorti-ligne"> -  already said about this - ${echapper(c.texte)}</div>`));
    }
    bloc.append(b);
  }

  const cadre = el(`<div class="fil-cadre"></div>`);
  const bas = el(`<button class="vers-le-bas" hidden>down Last message</button>`);
  bas.addEventListener("click", () => bloc.scrollTo({ top: bloc.scrollHeight, behavior: "smooth" }));
  const jauger = () => { bas.hidden = bloc.scrollHeight - bloc.scrollTop - bloc.clientHeight < 24; };
  bloc.addEventListener("scroll", jauger);
  cadre.append(bloc, bas);
  chat.append(cadre);

  const nouveaute = tours.length !== dernierFilIntendantRendu || (enAttenteIntendant && !dernierEnAttenteIntendantRendu);
  dernierFilIntendantRendu = tours.length;
  dernierEnAttenteIntendantRendu = enAttenteIntendant;
  setTimeout(() => { bloc.scrollTop = nouveaute ? bloc.scrollHeight : scrollAvant; jauger(); }, 0);


  const composeur = el(`
    <div class="composeur composeur-intendant">
      <textarea rows="2" placeholder="Meow.">${echapper(brouillonIntendant)}</textarea>
      <div class="colonne-envoi">
        <div class="ligne-modele">
          <label class="champ-fil champ-modele">
            <select>
              <option value="">- name a model -</option>
              ${(panier?.modeles ?? []).filter((m) => m.utilisable !== false).map((m) => `
                <option value="${echapper(m.id)}" ${m.id === agentChoisi() ? "selected" : ""}>
                  ${echapper(nomAgent(m.id))} - ${enGo(m.octets)} GB
                </option>`).join("")}
            </select>
          </label>
          ${anneauContexte()}
          ${atelier.vivant
            ? `<button class="bouton-decharger" title="Unload the model from RAM">Unload</button>`
            : ""}
        </div>
        <div class="boutons-envoi">
          <button class="envoyer" ${choisi ? "" : "disabled"}>${enAttenteIntendant ? "Queue it" : "Send"}</button>
          ${enAttenteIntendant ? `<button class="arreter-tour" title="Stop and get the message back to correct it">Stop</button>` : ""}
        </div>
      </div>
    </div>
  `);
  composeur.querySelector(".champ-modele select").addEventListener("change", (ev) => {
    choisirAgent(ev.target.value);
    dessiner();
  });
  brancherAnneau(composeur, {
    onCompacter: async () => {
      if (enAttenteIntendant) return;
      const rep = await api({ geste: "fil_neuf", modele: choisi?.id || "" });
      if (rep.fil) {
        filIntendant = rep.fil;
        localStorage.setItem(FIL_CLEF, rep.fil.id);
        dernierFilIntendantRendu = -1;
      }
      ressorti = { rappels: [], connexes: [] }; // they expire with the thread they described
      dessiner();
    },
  });
  composeur.querySelector(".bouton-decharger")?.addEventListener("click", async () => {
    await fetch("/api/arreter", { method: "POST" });
    await lireAtelier();
    dessiner();
  });
  const zone = composeur.querySelector("textarea");
  zone.addEventListener("input", () => { brouillonIntendant = zone.value; });

  const chrono = () => {
    const depart = Date.now();
    return setInterval(() => {
      const c = document.getElementById("chrono-i");
      if (c) c.textContent = `${((Date.now() - depart) / 1000).toFixed(1).replace(".", ",")} s`;
    }, 100);
  };

  const envoyer = async (texteFile) => {
    const texte = texteFile ?? zone.value.trim();
    if (!texte || !choisi || enAttenteIntendant) return;
    if (!texteFile) { zone.value = ""; brouillonIntendant = ""; }
    enVol = texte;   // visible right away, before the disk even carries it
    let cible = filIntendant;
    if (!cible) {
      const rep = await api({ geste: "fil_neuf", modele: choisi.id });
      cible = rep.fil ?? null;
      if (cible) { filIntendant = cible; localStorage.setItem(FIL_CLEF, cible.id); }
    }
    enAttenteIntendant = true;
    dessiner();
    const tic = chrono();
    const tailleAvant = cible?.tours?.length ?? 0;
    const sonde = setInterval(async () => {
      const rep = await api({ geste: "fil", id: cible?.id || "" });
      if (!rep.fil) return;
      filIntendant = rep.fil;
      if (filIntendant.tours.length > tailleAvant) enVol = "";
      dessiner();
    }, 2500);
    try {
      const dit = await api({
        geste: "parler",
        fil_id: cible?.id || "",
        modele: choisi.id,
        texte,
      });
      if (dit.etat !== "reponse") {
        chat.append(el(`
          <div class="refus"><b>${echapper(dit.genre || "refus")}</b>
            <div>${echapper(dit.detail || "")}</div></div>
        `));
      }
      ressorti = { rappels: dit.rappels ?? [], connexes: dit.connexes ?? [] };
      atelier = { ...atelier, ...dit };
    } finally {
      clearInterval(tic);
      clearInterval(sonde);
      enAttenteIntendant = false;
      await Promise.all([lireIntendant(), lireAtelier()]);
      enVol = "";
      dessiner();
    }
  };

  const deverserOuEnvoyer = () => {
    const texte = zone.value.trim();
    if (!texte) return;
    if (enAttenteIntendant) {
      messagesEnAttente.push(texte);
      zone.value = "";
      brouillonIntendant = "";
      dessiner();
    } else {
      envoyer();
    }
  };
  composeur.querySelector(".envoyer").addEventListener("click", deverserOuEnvoyer);
  zone.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); deverserOuEnvoyer(); }
  });
  composeur.querySelector(".arreter-tour")?.addEventListener("click", async (ev) => {
    const bouton = ev.currentTarget;
    bouton.disabled = true;
    bouton.textContent = "stopping...";
    brouillonIntendant = enVol;
    try { await fetch("/api/arreter", { method: "POST" }); } catch {  }
  });
  chat.append(composeur);

  if (messagesEnAttente.length) {
    const file = el(`<div class="file-attente"></div>`);
    messagesEnAttente.forEach((texte, i) => {
      const ligne = el(`
        <div class="file-attente-ligne">
          <div class="file-attente-texte">${echapper(texte)}</div>
          <button class="file-attente-envoyer" ${enAttenteIntendant ? "disabled" : ""}
            title="Send now" aria-label="Send now">^</button>
          <button class="file-attente-abandonner" title="Discard" aria-label="Discard">[no]</button>
        </div>
      `);
      ligne.querySelector(".file-attente-envoyer").addEventListener("click", () => {
        messagesEnAttente.splice(i, 1);
        envoyer(texte);
      });
      ligne.querySelector(".file-attente-abandonner").addEventListener("click", () => {
        messagesEnAttente.splice(i, 1);
        dessiner();
      });
      file.append(ligne);
    });
    chat.append(file);
  }

  if (avaitFocus) {
    setTimeout(() => {
      zone.focus();
      zone.setSelectionRange(selectionAvant[0], selectionAvant[1]);
    }, 0);
  } else if (!enAttenteIntendant) {
    setTimeout(() => zone.focus(), 0);
  }

  return scene;
}


function rendreConseiller() {
  const scene = document.createElement("div");
  scene.className = "scene-conseiller-liste";
  scene.style.setProperty("--panneau-largeur", `${largeurPanneau}px`);
  const chat = document.createElement("div");
  chat.className = "colonne-chat";
  const redimensionneur = el(`<div class="redimensionneur" title="Drag to resize"></div>`);
  brancherRedimensionneur(redimensionneur, scene);
  scene.append(chat, redimensionneur, rendreListeJalons());

  chat.append(el(`
    <header class="tete-vue tete-vue-compacte">
      <div class="tete-ligne">Mnémosyne <span aria-hidden="true">-</span> <b>The Advisor</b></div>
    </header>
  `));

  if (!conseiller || conseiller.etat !== "ok") {
    chat.append(el(`
      <div class="panne">
        <h2>The Advisor's store did not answer.</h2>
        <div>Nothing is displayed below: I prefer to show nothing rather than an
          empty store, which would read " you have no milestone ".</div>
        <pre>${echapper(conseiller?.detail || conseiller?.genre || "unexpected response")}</pre>
      </div>
    `));
    return scene;
  }

  const choisi = (panier?.modeles ?? []).find((m) => m.id === agentChoisi()) || null;

  const scrollAvant = document.querySelector(".fil")?.scrollTop ?? 0;
  const zoneAvant = document.querySelector(".composeur-conseiller textarea");
  const avaitFocus = zoneAvant != null && document.activeElement === zoneAvant;
  const selectionAvant = avaitFocus ? [zoneAvant.selectionStart, zoneAvant.selectionEnd] : null;
  const bloc = el(`<section class="fil"></section>`);
  const tours = filConseiller?.tours ?? [];
  if (!tours.length && !enAttenteConseiller) {
    bloc.append(el(`
      <div class="fil-vide">
        ${filConseiller
          ? `Empty thread. Tell it what is on your mind - it is listening.`
          : `No thread yet. Write below: it will open one.`}
      </div>
    `));
  }
  for (const tour of tours) {
    const deOperator = tour.role === "operator";
    const long = deOperator && tour.texte.length > SEUIL_REPLI && !tour.deplie;
    const b = el(`
      <div class="tour ${deOperator ? "de-operator" : "de-agent"}">
        <div class="tour-qui">${deOperator ? "You" : "The Advisor"}${
          tour.secondes != null ? `  -  ${tour.secondes}s` : ""
        }</div>
        <div class="tour-texte${long ? " coupe" : ""}">${echapper(tour.texte).replaceAll("\n", "<br>")}</div>
        ${long ? `<button class="voir-tout">See all - ${tour.texte.length.toLocaleString("fr-FR")} characters</button>` : ""}
      </div>
    `);
    b.querySelector(".voir-tout")?.addEventListener("click", () => { tour.deplie = true; dessiner(); });
    bloc.append(b);
  }
  if (enVolConseiller) {
    bloc.append(el(`
      <div class="tour de-operator en-vol">
        <div class="tour-qui">You</div>
        <div class="tour-texte">${echapper(enVolConseiller).replaceAll("\n", "<br>")}</div>
      </div>
    `));
  }
  if (enAttenteConseiller) {
    bloc.append(el(`
      <div class="tour de-agent attente-tour">
        <div class="tour-qui">The Advisor</div>
        <div class="tour-texte"><span class="chrono" id="chrono-c">0,0 s</span> - thinking...</div>
      </div>
    `));
  }
  if (ressortiConseiller.proches.length || ressortiConseiller.connexes.length) {
    const b = el(`<div class="ressorti"></div>`);
    for (const j of ressortiConseiller.proches) {
      b.append(el(`<div class="ressorti-ligne rappel"><- an approaching milestone - ${echapper(j.titre)}</div>`));
    }
    for (const c of ressortiConseiller.connexes) {
      b.append(el(`<div class="ressorti-ligne"> -  already said about this - ${echapper(c.titre)}</div>`));
    }
    bloc.append(b);
  }

  const cadre = el(`<div class="fil-cadre"></div>`);
  const bas = el(`<button class="vers-le-bas" hidden>down Last message</button>`);
  bas.addEventListener("click", () => bloc.scrollTo({ top: bloc.scrollHeight, behavior: "smooth" }));
  const jauger = () => { bas.hidden = bloc.scrollHeight - bloc.scrollTop - bloc.clientHeight < 24; };
  bloc.addEventListener("scroll", jauger);
  cadre.append(bloc, bas);
  chat.append(cadre);

  const nouveaute = tours.length !== dernierFilConseillerRendu || (enAttenteConseiller && !dernierEnAttenteConseillerRendu);
  dernierFilConseillerRendu = tours.length;
  dernierEnAttenteConseillerRendu = enAttenteConseiller;
  setTimeout(() => { bloc.scrollTop = nouveaute ? bloc.scrollHeight : scrollAvant; jauger(); }, 0);

  const composeur = el(`
    <div class="composeur composeur-conseiller">
      <textarea rows="2" placeholder="What is on your mind?">${echapper(brouillonConseiller)}</textarea>
      <div class="colonne-envoi">
        <div class="ligne-modele">
          <label class="champ-fil champ-modele">
            <select>
              <option value="">- name a model -</option>
              ${(panier?.modeles ?? []).filter((m) => m.utilisable !== false).map((m) => `
                <option value="${echapper(m.id)}" ${m.id === agentChoisi() ? "selected" : ""}>
                  ${echapper(nomAgent(m.id))} - ${enGo(m.octets)} GB
                </option>`).join("")}
            </select>
          </label>
          ${anneauContexte()}
          ${atelier.vivant
            ? `<button class="bouton-decharger" title="Unload the model from RAM">Unload</button>`
            : ""}
        </div>
        <div class="boutons-envoi">
          <button class="envoyer" ${choisi ? "" : "disabled"}>${enAttenteConseiller ? "Queue it" : "Send"}</button>
          ${enAttenteConseiller ? `<button class="arreter-tour" title="Stop and get the message back to correct it">Stop</button>` : ""}
        </div>
      </div>
    </div>
  `);
  composeur.querySelector(".champ-modele select").addEventListener("change", (ev) => {
    choisirAgent(ev.target.value);
    dessiner();
  });
  brancherAnneau(composeur, {
    onCompacter: async () => {
      if (enAttenteConseiller) return;
      const rep = await apiConseiller({ geste: "fil_neuf", modele: choisi?.id || "" });
      if (rep.fil) {
        filConseiller = rep.fil;
        localStorage.setItem(FIL_CONSEILLER_CLEF, rep.fil.id);
        dernierFilConseillerRendu = -1;
      }
      ressortiConseiller = { proches: [], connexes: [] };
      dessiner();
    },
  });
  composeur.querySelector(".bouton-decharger")?.addEventListener("click", async () => {
    await fetch("/api/arreter", { method: "POST" });
    await lireAtelier();
    dessiner();
  });
  const zone = composeur.querySelector("textarea");
  zone.addEventListener("input", () => { brouillonConseiller = zone.value; });

  const chrono = () => {
    const depart = Date.now();
    return setInterval(() => {
      const c = document.getElementById("chrono-c");
      if (c) c.textContent = `${((Date.now() - depart) / 1000).toFixed(1).replace(".", ",")} s`;
    }, 100);
  };

  const envoyer = async (texteFile) => {
    const texte = texteFile ?? zone.value.trim();
    if (!texte || !choisi || enAttenteConseiller) return;
    if (!texteFile) { zone.value = ""; brouillonConseiller = ""; }
    enVolConseiller = texte;
    let cible = filConseiller;
    if (!cible) {
      const rep = await apiConseiller({ geste: "fil_neuf", modele: choisi.id });
      cible = rep.fil ?? null;
      if (cible) { filConseiller = cible; localStorage.setItem(FIL_CONSEILLER_CLEF, cible.id); }
    }
    enAttenteConseiller = true;
    dessiner();
    const tic = chrono();
    const tailleAvant = cible?.tours?.length ?? 0;
    const sonde = setInterval(async () => {
      const rep = await apiConseiller({ geste: "fil", id: cible?.id || "" });
      if (!rep.fil) return;
      filConseiller = rep.fil;
      if (filConseiller.tours.length > tailleAvant) enVolConseiller = "";
      dessiner();
    }, 2500);
    try {
      const dit = await apiConseiller({
        geste: "parler",
        fil_id: cible?.id || "",
        modele: choisi.id,
        texte,
      });
      if (dit.etat !== "reponse") {
        chat.append(el(`
          <div class="refus"><b>${echapper(dit.genre || "refus")}</b>
            <div>${echapper(dit.detail || "")}</div></div>
        `));
      }
      ressortiConseiller = { proches: dit.jalons_proches ?? [], connexes: dit.connexes ?? [] };
      atelier = { ...atelier, ...dit };
    } finally {
      clearInterval(tic);
      clearInterval(sonde);
      enAttenteConseiller = false;
      await Promise.all([lireConseiller(), lireAtelier()]);
      enVolConseiller = "";
      dessiner();
    }
  };

  const deverserOuEnvoyer = () => {
    const texte = zone.value.trim();
    if (!texte) return;
    if (enAttenteConseiller) {
      messagesEnAttenteConseiller.push(texte);
      zone.value = "";
      brouillonConseiller = "";
      dessiner();
    } else {
      envoyer();
    }
  };
  composeur.querySelector(".envoyer").addEventListener("click", deverserOuEnvoyer);
  zone.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); deverserOuEnvoyer(); }
  });
  composeur.querySelector(".arreter-tour")?.addEventListener("click", async (ev) => {
    const bouton = ev.currentTarget;
    bouton.disabled = true;
    bouton.textContent = "stopping...";
    brouillonConseiller = enVolConseiller;
    try { await fetch("/api/arreter", { method: "POST" }); } catch {  }
  });
  chat.append(composeur);

  if (messagesEnAttenteConseiller.length) {
    const file = el(`<div class="file-attente"></div>`);
    messagesEnAttenteConseiller.forEach((texte, i) => {
      const ligne = el(`
        <div class="file-attente-ligne">
          <div class="file-attente-texte">${echapper(texte)}</div>
          <button class="file-attente-envoyer" ${enAttenteConseiller ? "disabled" : ""}
            title="Send now" aria-label="Send now">^</button>
          <button class="file-attente-abandonner" title="Discard" aria-label="Discard">[no]</button>
        </div>
      `);
      ligne.querySelector(".file-attente-envoyer").addEventListener("click", () => {
        messagesEnAttenteConseiller.splice(i, 1);
        envoyer(texte);
      });
      ligne.querySelector(".file-attente-abandonner").addEventListener("click", () => {
        messagesEnAttenteConseiller.splice(i, 1);
        dessiner();
      });
      file.append(ligne);
    });
    chat.append(file);
  }

  if (avaitFocus) {
    setTimeout(() => {
      zone.focus();
      zone.setSelectionRange(selectionAvant[0], selectionAvant[1]);
    }, 0);
  } else if (!enAttenteConseiller) {
    setTimeout(() => zone.focus(), 0);
  }

  return scene;
}



let dernierGesteJalon = null;

async function gesteConseiller(corps) {
  const rep = await apiConseiller(corps);
  if (rep.etat === "ok") conseiller = rep;
  await lireConseiller();
  dessiner();
  return rep;
}


function poserEcheanceJalon(jalon, corps) {
  if (jalon.echeance) {
    corps.append(el(`
      <div class="tache-echeance" data-echeance="${echapper(jalon.echeance)}">
        [pending] ${echapper(decompte(jalon.echeance) || "")}
      </div>
    `));
  } else {
    const definir = el(`<button class="tache-definir-echeance">set a due date</button>`);
    definir.addEventListener("click", () => {
      const input = el(`<input type="datetime-local" class="ajout-date">`);
      definir.replaceWith(input);
      input.focus();
      const valider = async () => {
        if (input.value) await gesteConseiller({ geste: "ranger", id: jalon.id, echeance: input.value });
        else dessiner();
      };
      input.addEventListener("change", valider);
      input.addEventListener("blur", valider);
    });
    corps.append(definir);
  }
}


function poserStatutJalon(jalon, corps) {
  const ligne = el(`<div class="jalon-statut-ligne"></div>`);
  const ouvrirEdition = () => {
    const input = el(`<input type="text" class="jalon-statut-champ" placeholder="where it stands...">`);
    input.value = jalon.statut || "";
    ligne.replaceChildren(input);
    input.focus();
    const valider = async () => {
      const v = input.value.trim();
      if (v && v !== jalon.statut) await gesteConseiller({ geste: "ranger", id: jalon.id, statut: v });
      else dessiner();
    };
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") valider();
      if (ev.key === "Escape") dessiner();
    });
    input.addEventListener("blur", valider);
  };
  if (jalon.statut) {
    ligne.append(el(`<span class="jalon-statut">${echapper(jalon.statut)}</span>`));
    const modifier = el(`<button class="jalon-modifier-statut" title="Edit the status" aria-label="Edit the status">[note]</button>`);
    modifier.addEventListener("click", ouvrirEdition);
    ligne.append(modifier);
  } else {
    const definir = el(`<button class="jalon-definir-statut">note where it stands</button>`);
    definir.addEventListener("click", ouvrirEdition);
    ligne.append(definir);
  }
  corps.append(ligne);
}

function rendreJalon(jalon) {
  const bloc = el(`
    <article class="tache jalon" data-id="${echapper(jalon.id)}">
      <div class="tache-ligne">
        <div class="tache-corps">
          <div class="tache-titre">
            <div class="tache-texte">${echapper(jalon.titre)}</div>
          </div>
        </div>
        <div class="tache-gestes">
          <button class="tache-retirer" title="Remove from the list (nothing is erased)">[no]</button>
        </div>
      </div>
    </article>
  `);
  const corps = bloc.querySelector(".tache-corps");
  poserEcheanceJalon(jalon, corps);
  poserStatutJalon(jalon, corps);
  bloc.querySelector(".tache-retirer").addEventListener("click", async () => {
    dernierGesteJalon = { id: jalon.id, titre: jalon.titre };
    await gesteConseiller({ geste: "marquer", id: jalon.id, nouvel_etat: "retiree" });
  });
  return bloc;
}

function rendreListeJalons() {
  const panneau = el(`<aside class="panneau-liste panneau-jalons"></aside>`);

  if (!conseiller || conseiller.etat !== "ok") {
    panneau.append(el(`
      <div class="panne panne-etroite">
        <h2>The list did not answer.</h2>
        <div>I prefer to show nothing rather than an empty list, which would read
          " you have no milestone ".</div>
        <pre>${echapper(conseiller?.detail || conseiller?.genre || "unexpected response")}</pre>
      </div>
    `));
    return panneau;
  }

  if (dernierGesteJalon) {
    const barre = el(`
      <div class="annulable">
        <span>[no] removed - ${echapper(dernierGesteJalon.titre)}</span>
        <button class="annulable-annuler">Undo</button>
        <button class="annulable-fermer" title="Close" aria-label="Close">[no]</button>
      </div>
    `);
    barre.querySelector(".annulable-annuler").addEventListener("click", async () => {
      const id = dernierGesteJalon.id;
      dernierGesteJalon = null;
      await gesteConseiller({ geste: "marquer", id, nouvel_etat: "vive" });
    });
    barre.querySelector(".annulable-fermer").addEventListener("click", () => {
      dernierGesteJalon = null;
      dessiner();
    });
    panneau.append(barre);
  }

  const ligne = el(`<div class="ajout-ligne"></div>`);
  const champ = el(`<input class="ajout" type="text" placeholder="+ new milestone">`);
  const dateChamp = el(`<input class="ajout-date" type="datetime-local">`);
  const poser = async () => {
    const texte = champ.value.trim();
    if (!texte) return;
    champ.value = "";
    const echeance = dateChamp.value;
    dateChamp.value = "";
    await gesteConseiller({ geste: "jalon", texte, echeance });
    document.querySelector(".panneau-jalons .ajout")?.focus();
  };
  champ.addEventListener("keydown", (ev) => { if (ev.key === "Enter") poser(); });
  ligne.append(champ, dateChamp);
  panneau.append(ligne);

  const jalons = conseiller.jalons ?? [];
  const liste = el(`<div class="taches jalons-liste"></div>`);
  if (!jalons.length) {
    liste.append(el(`<div class="section-vide">No milestone for now.</div>`));
  }
  for (const j of jalons) liste.append(rendreJalon(j));
  panneau.append(liste);
  return panneau;
}



const ETIQUETTE_SECTION = {
  deadline: "Deadlines",
  todo: "To-do",
  routine: "Routine",
  sans: "To sort",
};


const SECTIONS = ["routine", "deadline", "todo"];


const sousOuvertes = new Set();
const verbatimOuverts = new Set();


const TACHES_PLI_CLEF = "mnemosyne-ui/taches-repliees";

function lireTachesRepliees() {
  try {
    const brut = JSON.parse(localStorage.getItem(TACHES_PLI_CLEF));
    return new Set(Array.isArray(brut) ? brut : []);
  } catch {
    return new Set();
  }
}

function ecrireTachesRepliees() {
  try {
    localStorage.setItem(TACHES_PLI_CLEF, JSON.stringify([...tachesRepliees]));
  } catch {

  }
}

const tachesRepliees = lireTachesRepliees();


let dernierGeste = null;


const SECTIONS_PLI_CLEF = "mnemosyne-ui/sections-repliees";

function lireSectionsRepliees() {
  try {
    const brut = JSON.parse(localStorage.getItem(SECTIONS_PLI_CLEF));
    return new Set(Array.isArray(brut) ? brut : []);
  } catch {
    return new Set();
  }
}

function ecrireSectionsRepliees() {
  try {
    localStorage.setItem(SECTIONS_PLI_CLEF, JSON.stringify([...sectionsRepliees]));
  } catch {

  }
}

const sectionsRepliees = lireSectionsRepliees();

async function gesteListe(corps) {
  const rep = await api(corps);
  if (rep.etat === "ok") intendant = rep;
  await lireIntendant();
  dessiner();
  return rep;
}


function decompte(iso) {
  if (!iso) return null;
  const cible = Date.parse(iso);
  if (Number.isNaN(cible)) return null;
  const delta = cible - Date.now();
  if (delta <= 0) return "overdue";
  const minutes = Math.floor(delta / 60000);
  const jours = Math.floor(minutes / 1440);
  const heures = Math.floor((minutes % 1440) / 60);
  const reste = minutes % 60;
  if (jours > 0) return `${jours} d ${heures} h`;
  if (heures > 0) return `${heures} h ${reste} min`;
  return `${Math.max(reste, 1)} min`;
}

function rendreListePanneau() {
  const panneau = el(`<aside class="panneau-liste"></aside>`);

  if (!intendant || intendant.etat !== "ok") {
    panneau.append(el(`
      <div class="panne panne-etroite">
        <h2>The list did not answer.</h2>
        <div>I prefer to show nothing rather than an empty list, which would read
          " you have nothing to do ".</div>
        <pre>${echapper(intendant?.detail || intendant?.genre || "unexpected response")}</pre>
      </div>
    `));
    return panneau;
  }

  if (dernierGeste) {
    const barre = el(`
      <div class="annulable">
        <span>${dernierGeste.etat === "faite" ? "[ok] done" : "[no] removed"}${
          dernierGeste.touches.length > 1 ? ` - and ${dernierGeste.touches.length - 1} subtask(s)` : ""
        }</span>
        <button class="annulable-annuler">Undo</button>
        <button class="annulable-fermer" title="Close" aria-label="Close">[no]</button>
      </div>
    `);
    barre.querySelector(".annulable-annuler").addEventListener("click", async () => {
      const ids = dernierGeste.touches;
      dernierGeste = null;
      await gesteListe({ geste: "marquer", ids, nouvel_etat: "vive" });
    });
    barre.querySelector(".annulable-fermer").addEventListener("click", () => {
      dernierGeste = null;
      dessiner();
    });
    panneau.append(barre);
  }


  const notes = intendant.notes ?? [];
  const connus = new Set(notes.map((n) => n.id));
  const enfants = new Map();
  for (const n of notes) {
    if (n.parent && connus.has(n.parent)) {
      if (!enfants.has(n.parent)) enfants.set(n.parent, []);
      enfants.get(n.parent).push(n);
    }
  }
  for (const liste of enfants.values()) {
    liste.sort((a, b) => {
      if (a.ordre == null && b.ordre == null) return 0;
      if (a.ordre == null) return -1;
      if (b.ordre == null) return 1;
      return a.ordre - b.ordre;
    });
  }

  const groupes = intendant.par_horizon ?? {};
  const sections = [...SECTIONS];

  if ((groupes.sans ?? []).length) sections.push("sans");

  for (const clef of sections) panneau.append(rendreSection(clef, groupes[clef] ?? [], enfants));
  return panneau;
}


function brancherReordonnable(liste, onReordonner) {
  let traine = null;
  liste.addEventListener("dragstart", (ev) => {
    const poignee = ev.target.closest(".tache-glisser");
    if (!poignee) { ev.preventDefault(); return; }
    ev.stopPropagation();
    traine = poignee.closest(".tache");
    if (!traine) return;
    traine.classList.add("en-glisse");
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setDragImage(traine, 12, 12);
  });
  liste.addEventListener("dragover", (ev) => {
    if (!traine) return;
    ev.preventDefault();
    ev.stopPropagation();
    const apres = [...liste.children].find((n) => {
      if (n === traine || !n.classList.contains("tache")) return false;
      const r = n.getBoundingClientRect();
      return ev.clientY < r.top + r.height / 2;
    });
    if (apres) liste.insertBefore(traine, apres);
    else liste.appendChild(traine);
  });
  liste.addEventListener("drop", (ev) => ev.preventDefault());
  liste.addEventListener("dragend", (ev) => {
    if (!traine) return;
    ev.stopPropagation();
    traine.classList.remove("en-glisse");
    const ordre = [...liste.children]
      .filter((n) => n.classList.contains("tache"))
      .map((n) => n.dataset.id);
    traine = null;
    onReordonner(ordre);
  });
}

function rendreSection(clef, racines, enfants) {

  const triees = clef === "deadline"
    ? [...racines].sort((a, b) => {
        const ta = Date.parse(a.echeance || "");
        const tb = Date.parse(b.echeance || "");
        if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
        if (Number.isNaN(ta)) return 1;
        if (Number.isNaN(tb)) return -1;
        return ta - tb;
      })
    : racines;

  const repliee = sectionsRepliees.has(clef);
  const section = el(`
    <section class="section-liste section-${clef}${repliee ? " repliee" : ""}">
      <button class="section-tete" aria-expanded="${!repliee}">
        <span class="chevron"></span>
        <h2>${echapper(ETIQUETTE_SECTION[clef])}</h2>
        <span class="section-n">${triees.length || ""}</span>
      </button>
      <div class="section-corps"><div class="section-dedans"></div></div>
    </section>
  `);
  section.querySelector(".section-tete").addEventListener("click", () => {
    if (sectionsRepliees.has(clef)) sectionsRepliees.delete(clef);
    else sectionsRepliees.add(clef);
    ecrireSectionsRepliees();
    dessiner();
  });

  const dedans = section.querySelector(".section-dedans");


  if (clef !== "sans") {
    const ligne = el(`<div class="ajout-ligne"></div>`);
    const champ = el(`<input class="ajout" type="text" placeholder="${
      clef === "deadline" ? "+ new deadline" : "+ add a task"
    }">`);
    const dateChamp = clef === "deadline" ? el(`<input class="ajout-date" type="datetime-local">`) : null;
    const poser = async () => {
      const texte = champ.value.trim();
      if (!texte) return;
      champ.value = "";
      const echeance = dateChamp ? dateChamp.value : "";
      if (dateChamp) dateChamp.value = "";
      await gesteListe({ geste: "tache", texte, horizon: clef, echeance });
      document.querySelector(`.section-${clef} .ajout`)?.focus();
    };
    champ.addEventListener("keydown", (ev) => { if (ev.key === "Enter") poser(); });
    ligne.append(champ);
    if (dateChamp) ligne.append(dateChamp);
    dedans.append(ligne);
  }

  const liste = el(`<div class="taches"></div>`);
  if (!triees.length) {
    liste.append(el(`<div class="section-vide">${
      clef === "sans" ? "Empty." : "Nothing for now."
    }</div>`));
  }
  for (const t of triees) liste.append(rendreTache(t, enfants, 0));
  dedans.append(liste);
  if (clef !== "deadline") {
    brancherReordonnable(liste, (ordre) => gesteListe({ geste: "reordonner", ids: ordre }));
  }
  return section;
}

function rendreTache(note, enfants, profondeur) {
  return profondeur === 0 ? rendreTacheRacine(note, enfants) : rendreSousTache(note, enfants, profondeur);
}


function poserVerbatim(note, libelle, titre, corps) {
  const estVerbatim = libelle !== note.texte;
  const enPlus = estVerbatim ? note.texte : (note.description || "").trim();
  if (!enPlus) return;
  const mot = estVerbatim ? "the original text" : "the description";
  const ouvert = verbatimOuverts.has(note.id);
  const point = el(`
    <button class="tache-point${ouvert ? " ouvert" : ""}"
      title="${ouvert ? "Hide" : "Show"} ${mot}"
      aria-label="${ouvert ? "Hide" : "Show"} ${mot}"></button>
  `);
  point.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (verbatimOuverts.has(note.id)) verbatimOuverts.delete(note.id);
    else verbatimOuverts.add(note.id);
    dessiner();
  });
  titre.append(point);
  if (ouvert) corps.append(el(`<div class="tache-verbatim">${echapper(enPlus)}</div>`));
}


function poserCorpsCommun(note, corps) {
  if (note.horizon === "deadline") {
    if (note.echeance) {
      corps.append(el(`
        <div class="tache-echeance" data-echeance="${echapper(note.echeance)}">
          [pending] ${echapper(decompte(note.echeance) || "")}
        </div>
      `));
    } else {
      const definir = el(`<button class="tache-definir-echeance">set a due date</button>`);
      definir.addEventListener("click", () => {
        const input = el(`<input type="datetime-local" class="ajout-date">`);
        definir.replaceWith(input);
        input.focus();
        const valider = async () => {
          if (input.value) await gesteListe({ geste: "ranger", id: note.id, echeance: input.value });
          else dessiner();
        };
        input.addEventListener("change", valider);
        input.addEventListener("blur", valider);
      });
      corps.append(definir);
    }
  }
}


function rendreTacheRacine(note, enfants) {
  const filles = enfants.get(note.id) ?? [];
  const libelle = note.genre === "tache" && !note.resume ? note.texte : (note.resume || note.texte);
  const repliee = tachesRepliees.has(note.id);
  const bloc = el(`
    <article class="tache tache-racine${repliee ? " repliee" : ""}" data-id="${echapper(note.id)}">
      <div class="tache-entete">
        ${note.horizon === "deadline" ? "" : `<button class="tache-glisser" draggable="true" title="Drag to reorder" aria-label="Reorder">::</button>`}
        <button class="tache-toggle" aria-expanded="${!repliee}" title="${repliee ? "Expand" : "Collapse"}">
          <span class="chevron"></span>
        </button>
        <div class="tache-corps">
          <div class="tache-titre">
            <div class="tache-texte">${echapper(libelle)}</div>
          </div>
        </div>
        <span class="tache-n">${filles.length || ""}</span>
        <div class="tache-gestes">
          <button class="tache-fait" title="Mark done" aria-label="Mark done">[ok]</button>
          <button class="tache-plus" title="Add a subtask">+</button>
          <button class="tache-retirer" title="Remove from the list (nothing is erased)">[no]</button>
        </div>
      </div>
      <div class="tache-sous-corps"><div class="tache-sous-dedans"></div></div>
    </article>
  `);
  const corps = bloc.querySelector(".tache-entete .tache-corps");
  const titre = bloc.querySelector(".tache-entete .tache-titre");
  const dedans = bloc.querySelector(".tache-sous-dedans");
  poserVerbatim(note, libelle, titre, corps);
  poserCorpsCommun(note, corps);

  const vers = el(`<div class="tache-vers"></div>`);
  for (const clef of SECTIONS) {
    if (clef === note.horizon) continue;
    const b = el(`<button title="Move to ${echapper(ETIQUETTE_SECTION[clef].toLowerCase())}">${
      echapper(ETIQUETTE_SECTION[clef])
    }</button>`);
    b.addEventListener("click", () => gesteListe({ geste: "deplacer", id: note.id, horizon: clef }));
    vers.append(b);
  }
  bloc.querySelector(".tache-gestes").prepend(vers);

  const basculer = () => {
    if (tachesRepliees.has(note.id)) tachesRepliees.delete(note.id);
    else tachesRepliees.add(note.id);
    ecrireTachesRepliees();
    dessiner();
  };
  bloc.querySelector(".tache-toggle").addEventListener("click", basculer);
  corps.querySelector(".tache-texte").addEventListener("click", basculer);

  const marquer = async (etat) => {
    const rep = await api({ geste: "marquer", id: note.id, nouvel_etat: etat });
    dernierGeste = { etat, touches: rep.touches ?? [note.id] };
    if (rep.etat === "ok") intendant = rep;
    await lireIntendant();
    dessiner();
  };
  bloc.querySelector(".tache-fait").addEventListener("click", () => marquer("faite"));
  bloc.querySelector(".tache-retirer").addEventListener("click", () => marquer("retiree"));
  bloc.querySelector(".tache-plus").addEventListener("click", () => {
    if (sousOuvertes.has(note.id)) sousOuvertes.delete(note.id);
    else sousOuvertes.add(note.id);
    if (tachesRepliees.has(note.id)) { tachesRepliees.delete(note.id); ecrireTachesRepliees(); }
    dessiner();
  });

  const sous = el(`<div class="sous-taches"></div>`);
  for (const f of filles) sous.append(rendreTache(f, enfants, 1));
  dedans.append(sous);
  brancherReordonnable(sous, (ordre) => gesteListe({ geste: "reordonner", ids: ordre }));
  if (sousOuvertes.has(note.id)) {
    const champ = el(`<input class="ajout ajout-sous" type="text" placeholder="+ subtask">`);
    champ.addEventListener("keydown", async (ev) => {
      if (ev.key === "Escape") { sousOuvertes.delete(note.id); dessiner(); return; }
      if (ev.key !== "Enter") return;
      const texte = champ.value.trim();
      if (!texte) return;
      champ.value = "";
      await gesteListe({ geste: "tache", texte, parent: note.id });
      document.querySelector(`.tache[data-id="${note.id}"] .ajout-sous`)?.focus();
    });
    dedans.append(champ);
    setTimeout(() => dedans.querySelector(".ajout-sous")?.focus(), 0);
  } else if (!filles.length) {
    dedans.append(el(`<div class="section-vide">No subtask for now.</div>`));
  }
  return bloc;
}


function rendreSousTache(note, enfants, profondeur) {
  const filles = enfants.get(note.id) ?? [];
  const libelle = note.genre === "tache" && !note.resume ? note.texte : (note.resume || note.texte);
  const bloc = el(`
    <article class="tache" data-id="${echapper(note.id)}">
      <div class="tache-ligne">
        <button class="tache-glisser" draggable="true" title="Drag to reorder" aria-label="Reorder">::</button>
        <button class="coche" title="Mark done" aria-label="Mark done"></button>
        <div class="tache-corps">
          <div class="tache-titre">
            <div class="tache-texte">${echapper(libelle)}</div>
          </div>
        </div>
        <div class="tache-gestes">
          <button class="tache-plus" title="Add a subtask">+</button>
          <button class="tache-retirer" title="Remove from the list (nothing is erased)">[no]</button>
        </div>
      </div>
    </article>
  `);
  const corps = bloc.querySelector(".tache-corps");
  const titre = bloc.querySelector(".tache-titre");
  poserVerbatim(note, libelle, titre, corps);
  poserCorpsCommun(note, corps);

  const marquer = async (etat) => {
    const rep = await api({ geste: "marquer", id: note.id, nouvel_etat: etat });
    dernierGeste = { etat, touches: rep.touches ?? [note.id] };
    if (rep.etat === "ok") intendant = rep;
    await lireIntendant();
    dessiner();
  };
  bloc.querySelector(".coche").addEventListener("click", () => marquer("faite"));
  bloc.querySelector(".tache-retirer").addEventListener("click", () => marquer("retiree"));
  bloc.querySelector(".tache-plus").addEventListener("click", () => {
    if (sousOuvertes.has(note.id)) sousOuvertes.delete(note.id);
    else sousOuvertes.add(note.id);
    dessiner();
  });

  if (filles.length || sousOuvertes.has(note.id)) {
    const sous = el(`<div class="sous-taches"></div>`);
    for (const f of filles) sous.append(rendreTache(f, enfants, profondeur + 1));
    brancherReordonnable(sous, (ordre) => gesteListe({ geste: "reordonner", ids: ordre }));
    if (sousOuvertes.has(note.id)) {
      const champ = el(`<input class="ajout ajout-sous" type="text" placeholder="+ subtask">`);
      champ.addEventListener("keydown", async (ev) => {
        if (ev.key === "Escape") { sousOuvertes.delete(note.id); dessiner(); return; }
        if (ev.key !== "Enter") return;
        const texte = champ.value.trim();
        if (!texte) return;
        champ.value = "";
        await gesteListe({ geste: "tache", texte, parent: note.id });
        document.querySelector(`.tache[data-id="${note.id}"] .ajout-sous`)?.focus();
      });
      sous.append(champ);
      setTimeout(() => sous.querySelector(".ajout-sous")?.focus(), 0);
    }
    bloc.append(sous);
  }
  return bloc;
}


setInterval(() => {
  for (const noeud of document.querySelectorAll("[data-echeance]")) {
    const texte = decompte(noeud.dataset.echeance);
    if (texte !== null) noeud.textContent = `[pending] ${texte}`;
  }
}, 30_000);




const REPLIS_CLEF = "mnemosyne-ui/rail-replies";

function lireReplis() {
  try {
    const brut = localStorage.getItem(REPLIS_CLEF);
    return new Set(Array.isArray(JSON.parse(brut)) ? JSON.parse(brut) : []);
  } catch {
    return new Set(); // no storage (private mode, file://): everything is expanded.
  }
}

function ecrireReplis() {
  try {
    localStorage.setItem(REPLIS_CLEF, JSON.stringify([...replis]));
  } catch {

  }
}

const replis = lireReplis();

function construireRail() {
  const nav = document.getElementById("nav");
  nav.replaceChildren();

  const familles = [];


  const ajouter = (clef, titre) => {
    const replie = replis.has(clef);
    const bloc = el(`<section class="nav-famille${replie ? " replie" : ""}"></section>`);
    const tete = el(`
      <button class="nav-titre" aria-expanded="${!replie}">
        <span class="chevron" aria-hidden="true"></span>
        <span class="nav-titre-nom">${echapper(titre)}</span>
        <span class="nav-titre-alerte" hidden></span>
        <span class="nav-titre-n"></span>
      </button>
    `);

    const corps = el(`<div class="nav-corps"><div class="nav-dedans"></div></div>`);
    const dedans = corps.firstElementChild;

    tete.addEventListener("click", () => {
      const ouvert = tete.getAttribute("aria-expanded") === "true";
      tete.setAttribute("aria-expanded", String(!ouvert));
      bloc.classList.toggle("replie", ouvert);
      if (ouvert) replis.add(clef); else replis.delete(clef);
      ecrireReplis();
      marquer(famille);
    });

    bloc.append(tete, corps);
    nav.append(bloc);
    const famille = { bloc, tete, corps };
    familles.push(famille);
    return dedans;
  };


  const marquer = ({ bloc, tete, corps }) => {
    const n = corps.querySelectorAll(".nav-item").length;
    tete.querySelector(".nav-titre-n").textContent = n || "";
    const alerte = corps.querySelector(".pastille.alerte, .pastille.absent");
    const cache = bloc.classList.contains("replie");
    const marque = tete.querySelector(".nav-titre-alerte");
    marque.hidden = !(cache && alerte);
    marque.className = `nav-titre-alerte pastille ${alerte?.classList.contains("alerte") ? "alerte" : "absent"}`;
    marque.title = "An entry of this family could not be read.";
  };

  const bouton = ({ genre, clef, nom, compte, pastille }) => {
    const actif = vue.genre === genre && vue.clef === clef;
    const b = el(`
      <button class="nav-item" aria-current="${actif}">
        <span class="pastille ${pastille}"></span>
        <span class="nav-nom">${echapper(nom)}</span>
        <span class="nav-compte">${compte}</span>
      </button>
    `);
    b.addEventListener("click", () => {
      vue = { genre, clef };
      dessiner();
    });
    return b;
  };

  const systeme = ajouter("mnemosyne", "The system");
  const m = contrat.mnemosyne ?? {};
  const restants = (m.items ?? []).filter((i) => !CLOS_OU_FAIT.has(i.etat)).length;
  systeme.append(bouton({
    genre: "plan-mnemosyne",
    clef: null,
    nom: "System plan",
    compte: m.etat === "lisible" ? restants : "-",
    pastille: m.etat === "lisible" ? "vive" : "alerte",
  }));

  for (const f of contrat.files ?? []) {
    const lue = f.etat === "lue";
    const n = (f.items ?? []).length;
    systeme.append(bouton({
      genre: "file",
      clef: f.clef,
      nom: f.titre,
      compte: lue ? n : "?",
      pastille: !lue ? (f.etat === "absente" ? "absent" : "alerte")
        : f.clef === "runs_parques" && n ? "pret" : "",
    }));
  }

  const projets = contrat.projets ?? {};
  const bulles = ajouter("projets", "Projects");
  for (const p of projets.items ?? []) {
    const lisible = p.etat === "lisible";
    const reste = (p.items ?? []).filter((i) => !CLOS_OU_FAIT.has(i.etat)).length;
    bulles.append(bouton({
      genre: "projet",
      clef: p.nom,
      nom: p.nom,
      compte: lisible ? reste : (p.etat === "absent" ? "-" : "?"),
      pastille: lisible ? "" : (p.etat === "absent" ? "absent" : "alerte"),
    }));
  }

  if (projets.mal_placees?.length) {
    bulles.append(el(`
      <div class="nav-alerte">
        <span class="pastille alerte"></span>
        ${projets.mal_placees.length} misplaced bubble(s)
      </div>
    `));
  }

  for (const f of familles) marquer(f);
}



function dessiner() {
  const scene = document.getElementById("scene");
  construireRail();

  document.getElementById("vers-discussion")
    .setAttribute("aria-current", String(vue.genre === "discussion"));
  document.getElementById("vers-intendant")
    .setAttribute("aria-current", String(vue.genre === "intendant"));
  document.getElementById("vers-conseiller")
    .setAttribute("aria-current", String(vue.genre === "conseiller"));


  const aRanger = (intendant?.comptes?.deadline ?? 0) + (intendant?.comptes?.sans ?? 0);
  const pastille = document.getElementById("pastille-magasin");
  pastille.hidden = !aRanger;
  pastille.textContent = aRanger;

  let contenu;
  if (vue.genre === "intendant") {
    contenu = rendreIntendant();
  } else if (vue.genre === "conseiller") {
    contenu = rendreConseiller();
  } else if (vue.genre === "discussion") {
    contenu = rendreDiscussion();
  } else if (vue.genre === "file") {
    const f = (contrat.files ?? []).find((x) => x.clef === vue.clef);
    contenu = f ? rendreFile(f) : el(`<div class="vide">Queue not found.</div>`);
  } else if (vue.genre === "projet") {
    const p = (contrat.projets?.items ?? []).find((x) => x.nom === vue.clef);
    contenu = p ? rendrePlan(p, "Project") : el(`<div class="vide">Project not found.</div>`);
  } else {
    contenu = rendrePlan(contrat.mnemosyne ?? {}, "The system itself");
  }

  scene.replaceChildren(contenu);
  const cetteVue = `${vue.genre}:${vue.clef ?? ""}`;
  if (cetteVue !== derniereVueRendue) scene.scrollTop = 0;
  derniereVueRendue = cetteVue;
}

function montrerPanne(lecture) {
  document.getElementById("contrat-lu").textContent = "contract refused";
  document.getElementById("nav").replaceChildren();
  document.getElementById("scene").replaceChildren(el(`
    <div class="panne">
      <h2>${echapper(lecture.titre)}</h2>
      <div>Nothing is displayed below, and that is deliberate: I prefer to show nothing
      rather than show a state I could not read.</div>
      <pre>${echapper(lecture.detail)}</pre>
    </div>
  `));
}



async function relire() {
  const bouton = document.getElementById("relire");
  bouton.disabled = true;
  bouton.textContent = "reading...";

  try {
    const [rep, repPanier] = await Promise.all([
      fetch("/api/contrat", { cache: "no-store" }),
      fetch("/api/modeles", { cache: "no-store" }).catch(() => null),
      lireAtelier(),
      lireIntendant(),
    ]);
    panier = repPanier
      ? await repPanier.json().catch(() => null)
      : { _lecture: { ok: false, titre: "The local server did not return the basket.", detail: "" } };
    const donnees = await rep.json();

    if (!donnees._lecture?.ok) {
      montrerPanne(donnees._lecture ?? { titre: "Cannot read", detail: "Unexpected response." });
      document.getElementById("horodatage").textContent = "cannot read";
      return;
    }

    contrat = donnees;
    document.getElementById("horodatage").textContent = `read ${depuis(contrat.genere_le)}`;
    document.getElementById("contrat-lu").textContent =
      `${donnees._lecture.contrat} v${donnees._lecture.version}`;
    dessiner();
  } catch (err) {
    montrerPanne({
      titre: "The local server no longer responds.",
      detail: `${err}\n\nThe terminal window that launched the app may be closed.`,
    });
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Re-read the state";
  }
}


const PLI_CLEF = "mnemosyne-ui/rail-plie";

function poserPli(plie) {
  document.body.classList.toggle("rail-plie", plie);
  document.getElementById("rail-deplier").hidden = !plie;
  try { localStorage.setItem(PLI_CLEF, plie ? "1" : "0"); } catch {  }
}

try { poserPli(localStorage.getItem(PLI_CLEF) === "1"); } catch { poserPli(false); }
document.getElementById("rail-plier").addEventListener("click", () => poserPli(true));
document.getElementById("rail-deplier").addEventListener("click", () => poserPli(false));

document.getElementById("relire").addEventListener("click", relire);

document.getElementById("vers-discussion").addEventListener("click", () => {
  vue = { genre: "discussion", clef: null };
  dessiner();
});

document.getElementById("vers-intendant").addEventListener("click", async () => {
  vue = { genre: "intendant", clef: null };
  await lireIntendant();
  dernierFilIntendantRendu = -1;
  dessiner();
});

document.getElementById("vers-conseiller").addEventListener("click", async () => {
  vue = { genre: "conseiller", clef: null };
  await lireConseiller();
  dernierFilConseillerRendu = -1;
  dessiner();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") relire();
});

document.addEventListener("click", async (ev) => {
  const bouton = ev.target.closest("[data-copier]");
  if (!bouton) return;
  try {
    await navigator.clipboard.writeText(bouton.dataset.copier);
    bouton.classList.add("copie");
    setTimeout(() => bouton.classList.remove("copie"), 1400);
  } catch {

  }
});

relire();
