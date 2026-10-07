/* Prospective v2 payload and independent recovery reader. No pilot data. */
(() => {
  'use strict';
  let original = null;
  let originalClosed = false;
  let extras = [];
  let activeSpec = null;
  const stamp = () => performance.now();
  const announce = (kind, value = {}) => window.recordEvent({kind, page_ms: stamp(), ...value});
  const request = req => new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  const done = tx => new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve({completion_page_ms: stamp()});
    tx.onabort = () => reject(tx.error || Error('Transaction aborted'));
    tx.onerror = () => reject(tx.error || Error('Transaction failed'));
  });
  function openExisting(name, version) {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(name, version);
      req.onupgradeneeded = () => {req.transaction.abort(); reject(Error('Oracle refuses creation/upgrade'));};
      req.onerror = () => reject(req.error);
      req.onsuccess = () => resolve(req.result);
    });
  }
  async function oracle(spec) {
    const inventory = await indexedDB.databases();
    const descriptor = inventory.find(x => x.name === spec.database);
    if (!descriptor) return {endpoint: 'integrity_failure', reason: 'sentinel_database_absent', inventory};
    if (descriptor.version !== 1) return {endpoint: 'integrity_failure', reason: 'database_version', inventory};
    const db = await openExisting(spec.database, 1);
    try {
      const names = Array.from(db.objectStoreNames);
      if (JSON.stringify(names) !== JSON.stringify(['records']))
        return {endpoint: 'integrity_failure', reason: 'object_store_identity', names};
      const tx = db.transaction('records', 'readonly');
      const finished = done(tx);
      const store = tx.objectStore('records');
      if (store.keyPath !== 'id' || store.autoIncrement ||
          JSON.stringify(Array.from(store.indexNames)) !== JSON.stringify(['by_trial']) ||
          store.index('by_trial').keyPath !== 'trial' || store.index('by_trial').unique)
        return {endpoint: 'integrity_failure', reason: 'schema_identity'};
      // Issue every read synchronously while the transaction is active.
      const directReads = spec.targets.map(x => request(store.get(x.id)));
      const indexedRead = request(store.index('by_trial').getAll(spec.trial_id));
      const sentinelRead = request(store.get(spec.sentinel.id));
      const allRead = request(store.getAll());
      const direct = await Promise.all(directReads);
      const indexed = await indexedRead;
      const sentinel = await sentinelRead;
      const all = await allRead;
      await finished;
      const equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);
      if (!equal(sentinel, spec.sentinel)) return {endpoint: 'integrity_failure', reason: 'sentinel_invalid', sentinel, direct, indexed, all};
      const present = direct.filter(x => x !== undefined);
      if (present.length === 0 && indexed.length === 0 && all.length === 1)
        return {endpoint: 'lost', sentinel_valid: true, direct, indexed, all};
      if (present.length !== spec.targets.length || indexed.length !== spec.targets.length ||
          all.length !== spec.targets.length + 1 ||
          !spec.targets.every((x,i) => equal(direct[i],x)) ||
          !spec.targets.every(x => indexed.some(y => equal(x,y))))
        return {endpoint: 'integrity_failure', reason: 'target_content_metadata_checksum_or_multiplicity', direct, indexed, all};
      return {endpoint: 'recovered', sentinel_valid: true, direct, indexed, all};
    } finally {db.close();}
  }
  async function prepare(spec) {
    activeSpec = spec;
    if ((await indexedDB.databases()).some(x => x.name === spec.database))
      throw Error('Fresh profile precondition failed: database already exists');
    const req = indexedDB.open(spec.database, 1);
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore('records', {keyPath: 'id'});
      store.createIndex('by_trial', 'trial', {unique: false});
    };
    const db = await request(req);
    const tx = db.transaction('records','readwrite',{durability:'strict'});
    const finished = done(tx);
    const sentinelDurability = tx.durability;
    tx.objectStore('records').add(spec.sentinel);
    await finished;
    db.close();
    const readback = await oracle(spec);
    if (readback.endpoint !== 'lost' || !readback.sentinel_valid)
      throw Error('Strict sentinel/target-absence precondition failed');
    if (sentinelDurability !== 'strict') throw Error('Strict sentinel hint not honored');
    await announce('SENTINEL_INDEPENDENT_READBACK', {readback, durability_observed: sentinelDurability});
    return readback;
  }
  async function write(spec) {
    activeSpec = spec;
    original = await openExisting(spec.database,1);
    originalClosed = false;
    original.onclose = () => {originalClosed = true; announce('UNSOLICITED_CONNECTION_CLOSE');};
    if (spec.workload === 'four_connections') {
      for (let i=0; i<3; ++i) {
        const extra = await openExisting(spec.database,1);
        extra.onclose = () => announce('UNSOLICITED_EXTRA_CLOSE', {connection: i});
        extras.push(extra);
      }
    }
    const tx = original.transaction('records','readwrite',{durability: spec.durability});
    const finished = done(tx);
    const requested_ms = stamp();
    const observedDurability = tx.durability;
    for (const value of spec.targets) tx.objectStore('records').add(value);
    const completed = await finished;
    const ack_ms = stamp();
    announce('ACK', {ack_ms, requested_ms, completion_page_ms: completed.completion_page_ms,
                     durability_requested: spec.durability,
                     durability_observed: observedDurability, records: spec.targets.length,
                     original_closed: originalClosed, additional_connections: extras.length});
    if (spec.close_ms !== null) {
      const close = () => {
        announce('CLOSE_REQUEST', {ack_ms, assigned_close_ms: spec.close_ms});
        original.close(); originalClosed = true;
        announce('CLOSE_RETURNED', {ack_ms, assigned_close_ms: spec.close_ms,
                                  original_closed: originalClosed, additional_connections: extras.length});
      };
      if (spec.close_ms === 0) close();
      else setTimeout(close, Math.max(0,spec.close_ms-(stamp()-ack_ms)));
    }
    return {ack_ms, requested_ms};
  }
  window.v2 = {prepare,write,oracle,
    connectionState: () => ({original_closed: originalClosed, original_present: original!==null,
                             additional_connections: extras.length, trial_id: activeSpec?.trial_id}),
    clock: () => ({page_ms: stamp(), time_origin_ms: performance.timeOrigin})};
})();
