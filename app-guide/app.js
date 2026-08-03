const SOURCES = {
  appleFee: 'https://developer.apple.com/programs/whats-included/',
  appleDeveloperName: 'https://developer.apple.com/help/app-store-connect/create-an-app-record/set-your-developer-name/',
  appleEnrollment: 'https://developer.apple.com/help/account/membership/program-enrollment/',
  googleFee: 'https://support.google.com/googleplay/android-developer/answer/6112435',
  googleTesting: 'https://support.google.com/googleplay/android-developer/answer/14151465',
  googlePublicInfo: 'https://support.google.com/googleplay/android-developer/answer/13628312',
  googleAccountType: 'https://support.google.com/googleplay/android-developer/answer/13634885',
  googleChangeType: 'https://support.google.com/googleplay/android-developer/answer/16260648',
  japanShare: 'https://gs.statcounter.com/os-market-share/mobile/japan',
  worldShare: 'https://gs.statcounter.com/os-market-share/mobile/worldwide',
  appfiguresSpend: 'https://appfigures.com/resources/insights/20241018/amp?f=1',
};

// スマホOSの利用シェア(%)。出典: StatCounter Global Stats 月間データ。
// 更新するときは SOURCES.japanShare / SOURCES.worldShare の数字を見て
// asOf と数値を書き換えるだけでOK。
const SHARE = {
  asOf: '2026年7月',
  japan: { ios: 63.6, android: 36.4 },
  world: { ios: 31.6, android: 68.4 },
};

// 表示名・料金目安・リンク先。affiliate-config.json が読めたらそちらで上書きされる
// (アフィリエイトURLへの差し替えは affiliate-config.json を編集するだけでOK)
const AFFILIATE = {
  virtualOffice: { name: 'METSバーチャルオフィス', url: 'https://vo-metsoffice.jp/', priceNote: '月270円〜(住所利用のみのライトプラン)' },
  phone: { name: 'povo2.0', url: 'https://povo.jp/', priceNote: '基本料0円。半年に1回の少額トッピング(250円〜)で維持でき、月あたり数十円ほど' },
  disclosure: '※リンクには広告(PR)を含む場合があります。',
};
fetch('./affiliate-config.json')
  .then(r => r.ok ? r.json() : null)
  .then(cfg => {
    const jp = cfg?.offers?.JP;
    if (!jp) return;
    if (jp.virtualOffice) Object.assign(AFFILIATE.virtualOffice, jp.virtualOffice);
    if (jp.phone) Object.assign(AFFILIATE.phone, jp.phone);
    if (typeof jp.disclosure === 'string') AFFILIATE.disclosure = jp.disclosure;
    if (screen === 'googleOrgWarning') render();
  })
  .catch(() => {});

const NOTE_SECTIONS = {
  compare: [1, 'App StoreとGoogle Play、どちらに出す？'],
  accountTypes: [2, '個人アカウントと組織アカウントの違い'],
  businessBase: [3, '屋号・事業用住所・レンタルオフィスを考える'],
  openingNotice: [4, '開業届を出す前に決めておくこと'],
  duns: [5, 'D‑U‑N‑S番号の取得・住所確認'],
  appleNewIndividual: [6, 'Appleへ個人で新規登録する'],
  appleNewOrg: [7, 'Appleへ組織で新規登録する'],
  appleConvert: [8, 'Appleを個人から組織へ変更する'],
  googleNewIndividual: [9, 'Google Playへ個人で新規登録する'],
  googleNewOrg: [10, 'Google Playへ組織で新規登録する'],
  googleConvert: [11, 'Google Playを個人から組織へ変更する'],
  googleVerify: [12, 'Googleの組織確認で提出した書類'],
  etax: [13, 'e‑Tax受信通知を用意する'],
  pitfalls: [14, '実際につまずいたポイント'],
};

const INITIAL = {
  platform: null,
  appleStatus: null,
  appleDesired: null,
  appleNameOk: null,
  googleStatus: null,
  googleDesired: null,
  googleTesterOk: null,
  googlePublicInfoOk: null,
  wantSeparateAddress: null,
};

let state = structuredClone(INITIAL);
let screen = 'platform';
let historyStack = [];

const app = document.getElementById('app');
const resetTop = document.getElementById('resetTop');
resetTop.addEventListener('click', reset);

function source(href, label = '公式情報') {
  return `<a class="source-link" href="${href}" target="_blank" rel="noreferrer">${label} ↗</a>`;
}
function info(title, body, tone='neutral') {
  return `<div class="info-card ${tone}"><div class="info-card-title">${title}</div><div class="info-card-body">${body}</div></div>`;
}
function choice(title, desc='', action='') {
  return `<button class="choice" data-action="${action}"><div class="choice-copy"><strong>${title}</strong>${desc?`<span>${desc}</span>`:''}</div><div class="choice-arrow">›</div></button>`;
}

function shareRow(label, ios, android) {
  const i = Math.round(ios), a = Math.round(android);
  return `<div class="share-row">
    <div class="share-row-head"><span class="share-region">${label}</span><span class="share-values"><span class="share-value"><i class="dot dot-ios"></i>iPhone(iOS) <strong>${i}%</strong></span><span class="share-value"><i class="dot dot-android"></i>Android <strong>${a}%</strong></span></span></div>
    <div class="share-bar" role="img" aria-label="${label}のスマホOSシェア: iOS ${i}%、Android ${a}%"><div class="seg seg-ios" style="width:${ios}%"></div><div class="seg seg-android" style="width:${android}%"></div></div>
  </div>`;
}

function comparison() {
  return `<div class="comparison-wrap">
    <div class="share-block">
      <div class="share-block-title">スマホのOSシェア</div>
      <div class="share-block-sub">${SHARE.asOf}時点・StatCounter調べ(月間データ)</div>
      ${shareRow('日本', SHARE.japan.ios, SHARE.japan.android)}
      ${shareRow('世界', SHARE.world.ios, SHARE.world.android)}
    </div>
    <div class="comparison-card apple-card"><div class="comparison-heading">App Store</div><dl>
      <div><dt>対象</dt><dd>iPhone / iPad / Mac など</dd></div>
      <div><dt>登録料</dt><dd>年99米ドル(毎年)</dd></div>
      <div><dt>日本のシェア</dt><dd>iOS ${Math.round(SHARE.japan.ios)}%</dd></div>
      <div><dt>世界のシェア</dt><dd>iOS ${Math.round(SHARE.world.ios)}%</dd></div>
      <div><dt>課金の傾向</dt><dd>利用者の課金額が高め</dd></div>
    </dl></div>
    <div class="comparison-card google-card"><div class="comparison-heading">Google Play</div><dl>
      <div><dt>対象</dt><dd>Android</dd></div>
      <div><dt>登録料</dt><dd>25米ドル(最初の1回だけ)</dd></div>
      <div><dt>日本のシェア</dt><dd>Android ${Math.round(SHARE.japan.android)}%</dd></div>
      <div><dt>世界のシェア</dt><dd>Android ${Math.round(SHARE.world.android)}%</dd></div>
      <div><dt>課金の傾向</dt><dd>DL数と世界への広がりに強い</dd></div>
    </dl></div>
    <p class="fineprint">シェアは「スマホ端末のOS利用シェア」で、アプリ売上のシェアではありません。数字は毎月変わります。「課金の傾向」はAppfigures(2024年)などの調査を参考にした大まかな傾向で、アプリの種類や国によって変わります。</p>
    <div class="source-row">${source(SOURCES.japanShare,'日本のシェア(StatCounter)')}${source(SOURCES.worldShare,'世界のシェア(StatCounter)')}${source(SOURCES.appleFee,'Apple登録料')}${source(SOURCES.googleFee,'Google登録料')}${source(SOURCES.appfiguresSpend,'課金市場の参考')}</div>
  </div>`;
}

function go(next, patch={}) {
  historyStack.push({screen, state: structuredClone(state)});
  Object.assign(state, patch);
  screen = next;
  render();
  window.scrollTo({top:0, behavior:'smooth'});
}
function back() {
  const last = historyStack.pop();
  if (!last) return;
  screen = last.screen;
  state = last.state;
  render();
}
function reset() {
  state = structuredClone(INITIAL);
  screen = 'platform';
  historyStack = [];
  render();
}
function afterApple() { return state.platform === 'both' ? 'googleStatus' : 'address'; }
// Apple=個人のまま & Google=組織の人には、D-U-N-S等の準備が共通で使える
// 「App Storeも組織にする？」の提案を住所の質問の前に挟む
function afterGoogle() {
  const googleOrg = state.googleDesired === 'organization' || state.googleStatus === 'organization';
  const appleIndividual = state.platform === 'both' && ((state.appleStatus === 'none' && state.appleDesired === 'individual') || (state.appleStatus === 'individual' && state.appleDesired === 'keep'));
  return googleOrg && appleIndividual ? 'appleUpgradeOffer' : 'address';
}

function buildRoute() {
  const sections = [['compare', ...NOTE_SECTIONS.compare]];
  const steps = [];
  const cautions = [];
  const addSection = (key) => sections.push([key, ...NOTE_SECTIONS[key]]);

  if (['apple','both'].includes(state.platform)) {
    addSection('accountTypes');
    if (state.appleStatus === 'none') {
      if (state.appleDesired === 'individual') { addSection('appleNewIndividual'); steps.push('Apple Developer Programへ個人として登録する'); cautions.push('Appleの個人登録では、App Store上のデベロッパ名が原則として本人の法的な正式氏名になります。'); }
      if (state.appleDesired === 'organization') { addSection('businessBase'); addSection('duns'); addSection('appleNewOrg'); steps.push('Appleの組織登録要件を確認する','D‑U‑N‑S情報を整える','Appleへ組織として登録する'); }
    }
    if (state.appleStatus === 'individual') {
      if (state.appleDesired === 'keep') { addSection('appleNewIndividual'); steps.push('Apple個人アカウントをそのまま利用する'); cautions.push('個人アカウントではApp Store上に法的な正式氏名が表示されます。'); }
      if (state.appleDesired === 'organization') { addSection('businessBase'); addSection('duns'); addSection('appleConvert'); steps.push('Appleの組織変更要件を確認する','D‑U‑N‑S情報を整える','既存のAppleメンバーシップについて組織変更を申請する'); }
    }
    if (state.appleStatus === 'organization') steps.push('Appleは組織登録済み。組織名・住所・契約情報が現在も正しいか確認する');
  }
  if (['google','both'].includes(state.platform)) {
    addSection('accountTypes');
    if (state.googleStatus === 'none') {
      if (state.googleDesired === 'individual') { addSection('googleNewIndividual'); steps.push('Google Play Consoleへ個人として登録する','新規アプリの本番公開前テスト要件を満たす'); cautions.push('2023年11月13日以降に作成された新しい個人アカウントでは、原則12人以上が14日間連続で参加するクローズドテスト後に本番アクセス申請が必要です。'); cautions.push('Google Playでは個人アカウントでも一定の法的情報が公開され、収益化する場合は住所表示にも注意が必要です。'); }
      if (state.googleDesired === 'organization') { addSection('businessBase'); addSection('openingNotice'); addSection('duns'); addSection('googleNewOrg'); addSection('googleVerify'); steps.push('事業名・住所を整える','D‑U‑N‑S情報を整える','Google Paymentsの組織情報を用意する','Google Playへ組織として登録する'); }
    }
    if (state.googleStatus === 'individual') {
      if (state.googleDesired === 'keep') { addSection('googleNewIndividual'); steps.push('Google Play個人アカウントをそのまま利用する'); cautions.push('アカウント作成時期によって、新規アプリの本番公開前テスト要件を確認してください。'); }
      if (state.googleDesired === 'organization') { addSection('businessBase'); addSection('openingNotice'); addSection('duns'); addSection('googleConvert'); addSection('googleVerify'); addSection('etax'); steps.push('事業名・住所を整える','D‑U‑N‑SとGoogle Paymentsの情報を整える','Play Consoleから個人→組織変更を申請する','必要に応じて開業届＋e‑Tax受信通知など組織確認資料を提出する'); }
    }
    if (state.googleStatus === 'organization') steps.push('Google Playは組織登録済み。D‑U‑N‑S・Payments・組織情報が現在も一致しているか確認する');
  }
  if (state.wantSeparateAddress === true) { addSection('businessBase'); addSection('openingNotice'); steps.unshift('必要なら、開業届やD‑U‑N‑Sを整える前に事業用住所を決める'); }
  addSection('pitfalls');
  const sectionMap = new Map(); sections.forEach(([key,num,title]) => sectionMap.set(key,{key,num,title}));
  return {sections:[...sectionMap.values()].sort((a,b)=>a.num-b.num), steps:[...new Set(steps)], cautions:[...new Set(cautions)]};
}

function resultHtml() {
  const route = buildRoute();
  const appleText = ['apple','both'].includes(state.platform) ? (state.appleStatus==='organization'?'組織アカウント登録済み':state.appleDesired==='organization'?(state.appleStatus==='individual'?'個人 → 組織への変更ルート':'組織で新規登録するルート'):'個人アカウントを使うルート') : null;
  const googleText = ['google','both'].includes(state.platform) ? (state.googleStatus==='organization'?'組織アカウント登録済み':state.googleDesired==='organization'?(state.googleStatus==='individual'?'個人 → 組織への変更ルート':'組織で新規登録するルート'):'個人アカウントを使うルート') : null;
  return `${progressRow()}<div class="eyebrow">診断結果</div><h1>あなたが読むべきところを整理しました</h1><p class="lead">不要な章は飛ばしてOKです。実際の手続き前には各公式情報も確認してください。</p>
    <div class="result-grid">${appleText?`<div class="result-platform"><div><span>App Store</span><strong>${appleText}</strong></div></div>`:''}${googleText?`<div class="result-platform"><div><span>Google Play</span><strong>${googleText}</strong></div></div>`:''}</div>
    ${route.cautions.length?`<section class="result-section"><h2>⚠ 先に知っておきたい注意点</h2><ul>${route.cautions.map(c=>`<li>${c}</li>`).join('')}</ul></section>`:''}
    <section class="result-section"><h2>✓ やることリスト</h2><ol>${route.steps.map(s=>`<li>${s}</li>`).join('')}</ol></section>
    <section class="result-section note-section"><h2>📖 noteではこの章を読めばOK</h2><div class="chapter-list">${route.sections.map(s=>`<div class="chapter"><span>第${s.num}章</span><strong>${s.title}</strong></div>`).join('')}</div><p class="fineprint">公開後にnoteの各見出しURLが確定したら、この結果から該当見出しへ直接ジャンプするリンクを設定します。</p></section>
    ${state.wantSeparateAddress===true?info('事業用住所を分けたい人へ','レンタルオフィス等を使う予定なら、開業届・D‑U‑N‑S・ストア登録を進める前に住所を決めておくと、あとから住所変更を繰り返す手間を減らしやすくなります。','soft'):''}
    <div class="result-actions"><button class="primary-button" data-action="notePlaceholder">詳しい手順をnoteで読む ↗</button><button class="secondary-button" data-action="reset">↻ もう一度診断する</button></div>`;
}

// 進み具合のざっくり計算。分岐で質問数が変わるため正確な%ではなく、
// フェーズ(Apple区間/Google区間/住所)ごとの目安配分で出す。
function progressPercent() {
  if (screen === 'platform') return 5;
  if (screen === 'appleUpgradeOffer') return 87;
  if (screen === 'address') return 90;
  if (screen === 'result') return 100;
  const frac = {
    appleStatus:.15, appleExistingIndividual:.5, appleDesired:.45, appleDecisionHelp:.6, appleNameWarning:.8, appleOrgWarning:.8,
    googleStatus:.15, googleExistingIndividual:.5, googleDesired:.45, googleDecisionHelp:.6, googleTesterWarning:.65, googlePublicWarning:.85, googleOrgWarning:.8, googleExistingKeep:.8,
  };
  const isApple = screen.startsWith('apple');
  let lo = 10, hi = 85;
  if (state.platform === 'both') { if (isApple) { lo = 10; hi = 45; } else { lo = 45; hi = 85; } }
  return Math.round(lo + (hi - lo) * (frac[screen] ?? .5));
}
function progressRow() {
  const p = progressPercent();
  const label = p === 100 ? '完了! 100%' : `進み具合 だいたい${p}%`;
  return `<div class="progress-row"><div class="progress-track"><div class="progress-fill" style="width:${p}%"></div></div><span>${label}</span></div>`;
}

function page(body, eyebrow='', title='', lead='') { return `${progressRow()}${historyStack.length && screen!=='result'?'<button class="back-button" data-action="back">← 戻る</button>':''}${eyebrow?`<div class="eyebrow">${eyebrow}</div>`:''}${title?`<h1>${title}</h1>`:''}${lead?`<p class="lead">${lead}</p>`:''}${body}`; }

function render() {
  resetTop.classList.toggle('hidden', screen==='platform' || screen==='result');
  let html='';
  if (screen==='platform') html = page(`${comparison()}<div class="choices">${choice('App Storeだけ','iPhone / iPad / Macなど向け。日本はiPhone利用者が多め','platformApple')}${choice('Google Playだけ','Android向け。世界全体ではAndroid利用者が多め','platformGoogle')}${choice('両方','iPhoneとAndroidの両方に届けたい','platformBoth')}</div>`,'STEP 1','どこでアプリを公開したいですか？','まだ決めていなくても大丈夫。下の数字を、選ぶときの目安にしてください。');
  else if (screen==='appleStatus') html = page(`<div class="choices">${choice('まだ登録していない','','appleNone')}${choice('個人として登録済み','','appleIndividual')}${choice('会社・組織として登録済み','組織向けの手続きはほぼ完了しています','appleOrganization')}</div>`,'APPLE','Appleの開発者登録は、いまどの状態ですか？','App Storeでアプリを出すには「Apple Developer Program」というAppleの開発者アカウントが必要です。');
  else if (screen==='appleDesired') html = page(`${info('登録料',`Apple Developer Programは<strong>年99米ドル</strong>。毎年更新が必要です。 ${source(SOURCES.appleFee)}`,'soft')}<div class="choices">${choice('個人で登録する','手続きは簡単。ただし本名が公開されます(次の画面で説明)','appleWantIndividual')}${choice('組織で登録する','会社・団体向け。D‑U‑N‑S番号(会社を識別する国際的な番号)などの確認が必要','appleWantOrg')}${choice('まだ決められない','個人と組織の違いを先に見る','appleHelp')}</div>`,'APPLE / 新規登録','個人と組織、どちらで登録しますか？');
  else if (screen==='appleDecisionHelp') html = page(`${info('個人で登録すると',`App Storeの開発者名の欄に、原則として<strong>あなたの戸籍上の本名</strong>が表示されます。ニックネームや屋号にはできません。 ${source(SOURCES.appleDeveloperName)}`,'warning')}${info('組織で登録するには',`D‑U‑N‑S番号(会社を識別する国際的な番号)、契約できる権限、Webサイトなど、Appleが定める組織の条件を満たす必要があります。 ${source(SOURCES.appleEnrollment)}`,'soft')}<div class="choices">${choice('本名が表示されても問題ない','個人で登録する','appleWantIndividual')}${choice('条件を確認して組織で登録したい','組織で登録する','appleWantOrg')}</div>`,'APPLE / 個人と組織の違い','迷ったら「本名が表示されてもいいか」で考えるのが近道です');
  else if (screen==='appleNameWarning') html = page(`${info('個人登録の注意点',`Appleに個人で登録すると、App Store上の開発者名が原則として<strong>あなたの戸籍上の本名</strong>になります。 ${source(SOURCES.appleDeveloperName)}`,'warning')}<div class="choices">${choice('本名が表示されても問題ない','','appleNameOk')}${choice('本名は出したくない','組織で登録する場合の条件を確認します','appleNameNg')}</div>`,'APPLE / 大事な確認','App Storeにあなたの本名が表示されます。大丈夫ですか？');
  else if (screen==='appleOrgWarning') html = page(`${info('先に確認',`「開業届を出した」「屋号がある」だけでは、組織として登録できるとは限りません。D‑U‑N‑S番号(会社を識別する国際的な番号)や、契約できる法的な実体かどうかの確認が必要です。 ${source(SOURCES.appleEnrollment)}`,'warning')}<div class="choices">${choice('わかった。組織ルートで進む','','appleOrgContinue')}</div>`,'APPLE / 組織登録','Appleの組織登録には条件があります','組織登録を希望する場合は「D‑U‑N‑Sと事業情報を整える章」も案内します。');
  else if (screen==='appleExistingIndividual') html = page(`${info('個人のまま使う場合',`App Store上の開発者名は、原則としてあなたの戸籍上の本名のままです。 ${source(SOURCES.appleDeveloperName)}`,'warning')}<div class="choices">${choice('個人のまま使う','','appleKeep')}${choice('組織へ変更したい','変更の条件とD‑U‑N‑S番号を確認します','appleConvert')}</div>`,'APPLE / 登録済み','いまの個人アカウントを、どうしたいですか？');
  else if (screen==='googleStatus') html = page(`<div class="choices">${choice('まだ登録していない','','googleNone')}${choice('個人として登録済み','','googleIndividual')}${choice('会社・組織として登録済み','個人→組織の変更手続きは不要です','googleOrganization')}</div>`,'GOOGLE PLAY','Google Playの開発者登録は、いまどの状態ですか？','Google Playでアプリを出すには「Google Play Console」の開発者アカウントが必要です。');
  else if (screen==='googleDesired') html = page(`${info('登録料',`Google Play Consoleの登録料は<strong>25米ドル・最初の1回だけ</strong>です。 ${source(SOURCES.googleFee)}`,'soft')}<div class="choices">${choice('個人で登録する','手軽。ただし公開前テストと公開される情報に注意(次の画面で説明)','googleWantIndividual')}${choice('組織で登録する','会社・団体向け。D‑U‑N‑S番号(会社を識別する国際的な番号)などの確認が必要','googleWantOrg')}${choice('まだ決められない','個人と組織の注意点を比べて決める','googleHelp')}</div>`,'GOOGLE PLAY / 新規登録','個人と組織、どちらで登録しますか？');
  else if (screen==='googleDecisionHelp') html = page(`${info('個人で登録すると',`2023年11月13日より後に作られた新しい個人アカウントでは、初めてのアプリを公開する前に、原則として<strong>12人以上のテスターが14日間連続で参加するテスト</strong>が必要です。アップデートのたびに毎回必要になるわけではありません。 ${source(SOURCES.googleTesting)}`,'warning')}${info('組織で登録すると',`D‑U‑N‑S番号(会社を識別する国際的な番号)や、組織名・住所・Webサイトなどの確認が増えます。 ${source(SOURCES.googleAccountType)}`,'soft')}<div class="choices">${choice('テスターを12人集められそう','個人で登録する','googleWantIndividual')}${choice('組織の準備をして進めたい','組織で登録する','googleWantOrg')}</div>`,'GOOGLE PLAY / 個人と組織の違い','個人は手軽に見えて、「公開前テスト」が一番のハードルです');
  else if (screen==='googleTesterWarning') html = page(`${info('新しい個人アカウントの公開条件',`対象となる新しい個人アカウントでは、初めてのアプリを本番公開する前に、12人以上が14日間連続で参加するクローズドテストと、本番公開の申請が必要です。 ${source(SOURCES.googleTesting)}`,'warning')}<div class="choices">${choice('できそう / 問題ない','','googleTesterOk')}${choice('かなり大変そう…','組織で登録する場合の条件も見てみる','googleTesterNg')}</div>`,'GOOGLE PLAY / 確認 1','12人以上のテスターを、14日間続けて集められそうですか？');
  else if (screen==='googlePublicWarning') html = page(`${info('個人アカウントでも公開される情報があります',`Google Playでは、個人アカウントでも本名・国・連絡用メールアドレスなどが公開されます。さらに課金など収益化をする場合、住所が表示されるケースもあります。何が公開されるかを、事前に公式ヘルプで確認してください。 ${source(SOURCES.googlePublicInfo)}`,'warning')}<div class="choices">${choice('確認した。問題ない','','googlePublicOk')}${choice('公開される情報が気になる','組織で登録する場合の条件も見てみる','googlePublicNg')}</div>`,'GOOGLE PLAY / 確認 2','Google Playで公開されるあなたの情報も確認しましたか？');
  else if (screen==='googleOrgWarning') html = page(`${info('主な準備',`D‑U‑N‑S番号(会社を識別する国際的な番号)、組織名・住所、電話番号、Webサイト、Google Paymentsの組織情報などの確認が必要になります。 ${source(SOURCES.googleAccountType)}`,'soft')}${info('住所・電話番号などが公開されます',`組織アカウントでは、Google Play上の開発者情報として組織名・住所・電話番号などの連絡先が公開されます。自宅の住所や個人の電話番号をそのまま出したくない場合は、住所レンタル(バーチャルオフィス)や事業用の電話番号を用意する方法があります。 ${source(SOURCES.googlePublicInfo)}`,'warning')}${info('自宅住所・個人の電話を出したくない場合の費用の目安',`<ul class="cost-list"><li><strong>住所レンタル</strong> … ${AFFILIATE.virtualOffice.priceNote}。例: <a class="source-link" href="${AFFILIATE.virtualOffice.url}" target="_blank" rel="noreferrer sponsored">${AFFILIATE.virtualOffice.name} ↗</a></li><li><strong>電話番号</strong> … ${AFFILIATE.phone.priceNote}。例: <a class="source-link" href="${AFFILIATE.phone.url}" target="_blank" rel="noreferrer sponsored">${AFFILIATE.phone.name} ↗</a></li></ul>プランによって郵便物の受け取りや法人登記の可否が違うので、契約前に各サービスの内容を確認してください。<span class="disclosure">${AFFILIATE.disclosure}</span>`,'soft')}<p class="lead">すでに個人アカウントを持っている場合は、条件を満たせば個人→組織への変更手続きがあります。 ${source(SOURCES.googleChangeType,'変更手順')}</p><div class="choices">${choice('わかった。組織ルートで進む','','googleOrgContinue')}</div>`,'GOOGLE PLAY / 組織登録','Google Playの組織登録は、準備するものが少し増えます');
  else if (screen==='googleExistingIndividual') html = page(`<div class="choices">${choice('個人のまま使う','公開前テストと公開される情報が自分に当てはまるか確認します','googleKeep')}${choice('組織へ変更したい','いまのアカウントから変更できる場合があります','googleConvert')}</div>`,'GOOGLE PLAY / 登録済み','いまの個人アカウントを、どうしたいですか？');
  else if (screen==='googleExistingKeep') html = page(`${info('アカウントを作った時期を確認',`2023年11月13日より後に作った個人アカウントには、初めてのアプリを本番公開する前のテスト条件(12人×14日間)があります。 ${source(SOURCES.googleTesting)}`,'warning')}${info('公開される情報',`個人アカウントでも公開される情報(本名など)があります。収益化する場合の住所表示も含めて、現在の公式案内を確認してください。 ${source(SOURCES.googlePublicInfo)}`,'warning')}<div class="choices">${choice('確認した。個人のまま進む','','googleKeepContinue')}</div>`,'GOOGLE PLAY / 個人のまま使う','そのまま使う場合の確認ポイント');
  else if (screen==='appleUpgradeOffer') html = page(`${info('準備するものはGoogle Playとほぼ共通',`Google Playの組織登録で用意するもの(D‑U‑N‑S番号・事業情報など)は、Appleの組織登録でも<strong>ほぼそのまま使えます</strong>。追加の作業は主にApple側への申請です。組織にすると、App Storeにはあなたの本名ではなく<strong>組織名が表示されます</strong>。`,'soft')}${info('確認',`Apple公式は、個人事業主・一人事業には原則Individual(個人)での登録を案内しており、屋号や商号(DBA)はOrganizationとして認められません。変更を申請しても、必ず通るとは限らない点は知っておいてください。 ${source(SOURCES.appleEnrollment)}`,'warning')}<div class="choices">${choice('App Storeも組織にする','Google Play用の準備を使い回せて、本名表示も避けられます','appleUpgradeYes')}${choice('Appleは個人のままでいい','App Storeには本名が表示されます','appleUpgradeNo')}</div>`,'APPLE / ついでの提案','App Storeも組織アカウントにしませんか？','Google Playを組織で進めるなら、Appleを組織にする手間は小さくなります。');
  else if (screen==='address') html = page(`<div class="choices">${choice('はい。自宅とは別の住所を使いたい','開業届やD‑U‑N‑Sの前に決めておくと、あとで住所変更する二度手間を減らせます','addressYes')}${choice('いいえ。自宅の住所で問題ない','','addressNo')}${choice('まだ分からない','診断結果に「検討ポイント」として残します','addressMaybe')}</div>`,'最後の質問','事業用の住所を、自宅の住所と分けたいですか？','ストアやD‑U‑N‑Sに登録する住所の話です。全員にレンタルオフィスが必要なわけではありません。');
  else if (screen==='result') html = resultHtml();
  app.innerHTML = html;
}

app.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-action]'); if (!btn) return;
  const a = btn.dataset.action;
  if (a==='back') return back(); if (a==='reset') return reset(); if (a==='notePlaceholder') return alert('note公開後にここへ記事URLを設定してください。');
  const actions = {
    platformApple:()=>go('appleStatus',{platform:'apple'}), platformGoogle:()=>go('googleStatus',{platform:'google'}), platformBoth:()=>go('appleStatus',{platform:'both'}),
    appleNone:()=>go('appleDesired',{appleStatus:'none'}), appleIndividual:()=>go('appleExistingIndividual',{appleStatus:'individual'}), appleOrganization:()=>go(afterApple(),{appleStatus:'organization',appleDesired:'keep'}),
    appleWantIndividual:()=>go('appleNameWarning',{appleDesired:'individual'}), appleWantOrg:()=>go('appleOrgWarning',{appleDesired:'organization'}), appleHelp:()=>go('appleDecisionHelp'),
    appleNameOk:()=>go(afterApple(),{appleNameOk:true}), appleNameNg:()=>go('appleOrgWarning',{appleDesired:'organization',appleNameOk:false}), appleOrgContinue:()=>go(afterApple()), appleKeep:()=>go(afterApple(),{appleDesired:'keep'}), appleConvert:()=>go('appleOrgWarning',{appleDesired:'organization'}),
    googleNone:()=>go('googleDesired',{googleStatus:'none'}), googleIndividual:()=>go('googleExistingIndividual',{googleStatus:'individual'}), googleOrganization:()=>go(afterGoogle(),{googleStatus:'organization',googleDesired:'keep'}),
    googleWantIndividual:()=>go('googleTesterWarning',{googleDesired:'individual'}), googleWantOrg:()=>go('googleOrgWarning',{googleDesired:'organization'}), googleHelp:()=>go('googleDecisionHelp'),
    googleTesterOk:()=>go('googlePublicWarning',{googleTesterOk:true}), googleTesterNg:()=>go('googleOrgWarning',{googleDesired:'organization',googleTesterOk:false}), googlePublicOk:()=>go(afterGoogle(),{googlePublicInfoOk:true}), googlePublicNg:()=>go('googleOrgWarning',{googleDesired:'organization',googlePublicInfoOk:false}), googleOrgContinue:()=>go(afterGoogle()), googleKeep:()=>go('googleExistingKeep',{googleDesired:'keep'}), googleConvert:()=>go('googleOrgWarning',{googleDesired:'organization'}), googleKeepContinue:()=>go(afterGoogle()),
    appleUpgradeYes:()=>go('address',{appleDesired:'organization'}), appleUpgradeNo:()=>go('address'),
    addressYes:()=>go('result',{wantSeparateAddress:true}), addressNo:()=>go('result',{wantSeparateAddress:false}), addressMaybe:()=>go('result',{wantSeparateAddress:null}),
  };
  actions[a]?.();
});

render();
