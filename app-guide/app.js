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
function choice(title, desc='', action='', icon='›', recommended=false) {
  return `<button class="choice" data-action="${action}"><div class="choice-icon">${icon}</div><div class="choice-copy"><div class="choice-title-row"><strong>${title}</strong>${recommended?'<span class="pill">おすすめ</span>':''}</div>${desc?`<span>${desc}</span>`:''}</div><div>›</div></button>`;
}
function comparison() {
  return `<div class="comparison-wrap">
    <div class="comparison-card apple-card"><div class="comparison-heading"> App Store</div><dl><div><dt>登録料</dt><dd>年99米ドル</dd></div><div><dt>日本</dt><dd>iOSが強い市場</dd></div><div><dt>世界</dt><dd>Androidより端末シェアは小さい</dd></div><div><dt>課金</dt><dd>消費者支出が強い傾向</dd></div></dl></div>
    <div class="comparison-card google-card"><div class="comparison-heading">▶ Google Play</div><dl><div><dt>登録料</dt><dd>25米ドル・一度限り</dd></div><div><dt>日本</dt><dd>Androidも大きな利用層</dd></div><div><dt>世界</dt><dd>Androidが大きなシェア</dd></div><div><dt>課金</dt><dd>DL・世界リーチに強い</dd></div></dl></div>
    <p class="fineprint">OSシェアは時期・集計方法で変動します。課金傾向もカテゴリや国で異なるため、ここでは選択の目安として表示しています。</p>
    <div class="source-row">${source(SOURCES.appleFee,'Apple登録料')}${source(SOURCES.googleFee,'Google登録料')}${source(SOURCES.japanShare,'日本OSシェア')}${source(SOURCES.worldShare,'世界OSシェア')}${source(SOURCES.appfiguresSpend,'課金市場の参考')}</div>
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
function afterGoogle() { return 'address'; }

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
  return `<div class="eyebrow">診断結果</div><h1>あなたが読むべきところを整理しました</h1><p class="lead">不要な章は飛ばしてOKです。実際の手続き前には各公式情報も確認してください。</p>
    <div class="result-grid">${appleText?`<div class="result-platform"><div></div><div><span>App Store</span><strong>${appleText}</strong></div></div>`:''}${googleText?`<div class="result-platform"><div>▶</div><div><span>Google Play</span><strong>${googleText}</strong></div></div>`:''}</div>
    ${route.cautions.length?`<section class="result-section"><h2>⚠ 先に知っておきたい注意点</h2><ul>${route.cautions.map(c=>`<li>${c}</li>`).join('')}</ul></section>`:''}
    <section class="result-section"><h2>✓ あなたの手続き</h2><ol>${route.steps.map(s=>`<li>${s}</li>`).join('')}</ol></section>
    <section class="result-section note-section"><h2>📖 noteではこの章を読めばOK</h2><div class="chapter-list">${route.sections.map(s=>`<div class="chapter"><span>第${s.num}章</span><strong>${s.title}</strong></div>`).join('')}</div><p class="fineprint">公開後にnoteの各見出しURLが確定したら、この結果から該当見出しへ直接ジャンプするリンクを設定します。</p></section>
    ${state.wantSeparateAddress===true?info('事業用住所を分けたい人へ','レンタルオフィス等を使う予定なら、開業届・D‑U‑N‑S・ストア登録を進める前に住所を決めておくと、あとから住所変更を繰り返す手間を減らしやすくなります。','soft'):''}
    <div class="result-actions"><button class="primary-button" data-action="notePlaceholder">詳しい手順をnoteで読む ↗</button><button class="secondary-button" data-action="reset">↻ もう一度診断する</button></div>`;
}

function page(body, eyebrow='', title='', lead='') { return `${historyStack.length && screen!=='result'?'<button class="back-button" data-action="back">← 戻る</button>':''}${eyebrow?`<div class="eyebrow">${eyebrow}</div>`:''}${title?`<h1>${title}</h1>`:''}${lead?`<p class="lead">${lead}</p>`:''}${body}`; }

function render() {
  resetTop.classList.toggle('hidden', screen==='platform' || screen==='result');
  let html='';
  if (screen==='platform') html = page(`${comparison()}<div class="choices">${choice('App Storeだけ','iPhone / iPadを中心に公開したい','platformApple','')}${choice('Google Playだけ','Android向けに公開したい','platformGoogle','▶')}${choice('両方','iOSとAndroidの両方へ届けたい','platformBoth','◎',true)}</div>`,'STEP 1','どこでアプリを公開したいですか？','まだ決めていなくても大丈夫。費用・利用者の広さ・課金傾向を見て選べます。');
  else if (screen==='appleStatus') html = page(`<div class="choices">${choice('まだ登録していない','','appleNone','＋')}${choice('個人で登録済み','','appleIndividual','人')}${choice('組織で登録済み','組織化手続きは基本的に不要','appleOrganization','社')}</div>`,'APPLE','Apple Developer Programの現在の状態は？','「登録済み」の人にも、個人・組織それぞれのルートがあります。');
  else if (screen==='appleDesired') html = page(`${info('登録料',`Apple Developer Programは<strong>年99米ドル</strong>。毎年更新が必要です。 ${source(SOURCES.appleFee)}`,'soft')}<div class="choices">${choice('個人で登録したい','','appleWantIndividual','人')}${choice('組織で登録したい','D‑U‑N‑Sなど組織確認が必要','appleWantOrg','社')}${choice('まだ分からない','個人と組織の違いを先に確認する','appleHelp','?')}</div>`,'APPLE / 新規','個人と組織、どちらで登録したいですか？');
  else if (screen==='appleDecisionHelp') html = page(`${info('個人',`App Store上のデベロッパ名は、原則として<strong>本人の法的な正式氏名</strong>になります。 ${source(SOURCES.appleDeveloperName)}`,'warning')}${info('組織',`組織登録には、Appleが求める組織要件、D‑U‑N‑S番号、契約権限、Webサイト等が必要です。 ${source(SOURCES.appleEnrollment)}`,'soft')}<div class="choices">${choice('本名表示で問題ない → 個人','','appleWantIndividual')}${choice('組織要件を確認して進みたい → 組織','','appleWantOrg')}</div>`,'APPLE / 比較','迷ったら、まず「本名表示」を確認');
  else if (screen==='appleNameWarning') html = page(`${info('個人登録の注意点',`Appleの個人登録では、App Store上のデベロッパ名が原則として<strong>あなたの法的な正式氏名</strong>になります。 ${source(SOURCES.appleDeveloperName)}`,'warning')}<div class="choices">${choice('問題ない','','appleNameOk')}${choice('本名は出したくない','組織登録の条件を確認する','appleNameNg')}</div>`,'APPLE / 重要確認','本名がApp Store上に表示されても大丈夫ですか？');
  else if (screen==='appleOrgWarning') html = page(`${info('先に確認',`AppleのOrganizationは単に「屋号がある」「開業届を出した」というだけで自動的に選べるものではありません。D‑U‑N‑S番号や法的主体としての要件等を確認してください。 ${source(SOURCES.appleEnrollment)}`,'warning')}<div class="choices">${choice('理解した。組織ルートで進む','','appleOrgContinue')}</div>`,'APPLE / 組織','Appleの組織登録には条件があります','組織登録を希望する場合は「D‑U‑N‑Sと事業情報を整える章」も案内します。');
  else if (screen==='appleExistingIndividual') html = page(`${info('個人のまま使う場合',`App Store上のデベロッパ名は原則として法的な正式氏名です。 ${source(SOURCES.appleDeveloperName)}`,'warning')}<div class="choices">${choice('個人のまま使う','','appleKeep')}${choice('組織へ変更したい','変更要件・D‑U‑N‑Sを確認','appleConvert')}</div>`,'APPLE / 登録済み','今の個人アカウントをどうしたいですか？');
  else if (screen==='googleStatus') html = page(`<div class="choices">${choice('まだ登録していない','','googleNone','＋')}${choice('個人で登録済み','','googleIndividual','人')}${choice('組織で登録済み','個人→組織変更の章は不要','googleOrganization','社')}</div>`,'GOOGLE PLAY','Google Play Consoleの現在の状態は？');
  else if (screen==='googleDesired') html = page(`${info('登録料',`Google Play Consoleは<strong>25米ドルの一度限りの登録料</strong>です。 ${source(SOURCES.googleFee)}`,'soft')}<div class="choices">${choice('個人で登録したい','','googleWantIndividual','人')}${choice('組織で登録したい','D‑U‑N‑Sや組織確認が必要','googleWantOrg','社')}${choice('まだ分からない','注意点を比較して決める','googleHelp','?')}</div>`,'GOOGLE PLAY / 新規','個人と組織、どちらで登録したいですか？');
  else if (screen==='googleDecisionHelp') html = page(`${info('新しい個人アカウント',`2023年11月13日以降に作成された新しい個人アカウントでは、原則として<strong>12人以上のテスターが14日間連続で参加するクローズドテスト</strong>を完了してから、本番アクセスを申請します。通常のアップデートごとに毎回12人必要、という意味ではありません。 ${source(SOURCES.googleTesting)}`,'warning')}${info('組織アカウント',`組織ではD‑U‑N‑S番号、組織名・住所、Webサイトなどの確認が増えます。 ${source(SOURCES.googleAccountType)}`,'soft')}<div class="choices">${choice('12人×14日のテストを用意できる → 個人','','googleWantIndividual')}${choice('組織の準備をして進みたい → 組織','','googleWantOrg')}</div>`,'GOOGLE PLAY / 比較','個人は簡単そうに見えて、公開前テストが大きなポイント');
  else if (screen==='googleTesterWarning') html = page(`${info('新規個人アカウントの本番公開要件',`対象となる新しい個人アカウントでは、新規アプリの本番公開前に、12人以上が14日間連続で参加するクローズドテストと本番アクセス申請が必要です。 ${source(SOURCES.googleTesting)}`,'warning')}<div class="choices">${choice('できる / 問題ない','','googleTesterOk')}${choice('かなり大変そう','組織アカウントの要件も見る','googleTesterNg')}</div>`,'GOOGLE PLAY / 重要確認 1','12人以上のテスターを14日間用意できそうですか？');
  else if (screen==='googlePublicWarning') html = page(`${info('個人アカウントでも公開情報があります',`Google Playでは、個人アカウントでも法的氏名・国・デベロッパーメール等が公開対象になります。収益化する場合は完全な住所が表示されるケースもあるため、公開情報を事前に公式ヘルプで確認してください。 ${source(SOURCES.googlePublicInfo)}`,'warning')}<div class="choices">${choice('確認した。問題ない','','googlePublicOk')}${choice('公開情報が気になる','組織アカウントの要件も比較する','googlePublicNg')}</div>`,'GOOGLE PLAY / 重要確認 2','Google Playで公開される情報も確認しましたか？');
  else if (screen==='googleOrgWarning') html = page(`${info('主な準備',`D‑U‑N‑S番号、組織名・住所、電話番号、Webサイト、Google Paymentsの組織情報、組織確認などが必要になります。 ${source(SOURCES.googleAccountType)}`,'soft')}<p class="lead">すでに個人アカウントを持っている場合は、条件を満たせば個人→組織への変更フローがあります。 ${source(SOURCES.googleChangeType,'変更手順')}</p><div class="choices">${choice('理解した。組織ルートで進む','','googleOrgContinue')}</div>`,'GOOGLE PLAY / 組織','Google Playの組織登録は準備が少し増えます');
  else if (screen==='googleExistingIndividual') html = page(`<div class="choices">${choice('個人のまま使う','公開前テスト・公開情報の該当有無を確認','googleKeep')}${choice('組織へ変更したい','既存アカウントから変更できる場合があります','googleConvert')}</div>`,'GOOGLE PLAY / 登録済み','今の個人アカウントをどうしたいですか？');
  else if (screen==='googleExistingKeep') html = page(`${info('作成時期を確認',`2023年11月13日以降に作成された新しい個人アカウントでは、新規アプリの本番公開前テスト要件があります。 ${source(SOURCES.googleTesting)}`,'warning')}${info('公開情報',`個人アカウントでも公開される法的情報があります。収益化時の住所表示も含め、現在の公式案内を確認してください。 ${source(SOURCES.googlePublicInfo)}`,'warning')}<div class="choices">${choice('確認した。個人のまま進む','','googleKeepContinue')}</div>`,'GOOGLE PLAY / 個人継続','そのまま使う場合の確認ポイント');
  else if (screen==='address') html = page(`<div class="choices">${choice('はい。事業用住所を分けたい','開業届やD‑U‑N‑Sを整える前に決めると二度手間を減らせます','addressYes','社')}${choice('いいえ。自宅住所で問題ない','','addressNo','✓')}${choice('まだ分からない','結果に「検討ポイント」として残す','addressMaybe','?')}</div>`,'事業情報','事業で使う住所を、自宅と分けたいですか？','全員にレンタルオフィスが必要なわけではありません。住所を分けたい人だけ検討します。');
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
    addressYes:()=>go('result',{wantSeparateAddress:true}), addressNo:()=>go('result',{wantSeparateAddress:false}), addressMaybe:()=>go('result',{wantSeparateAddress:null}),
  };
  actions[a]?.();
});

render();
