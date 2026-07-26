<template>
  <div class="project-page">

    <!-- Top bar -->
    <div class="top-bar">
      <div class="breadcrumb">
        <button class="back-btn" @click="navigateTo('/')">
          <span class="back-chevron">‹</span>{{ t('projectCanvas.home') }}
        </button>
        <span class="bc-sep">/</span>
        <span class="bc-item">{{ project.work }}</span>
        <span class="bc-sep">·</span>
        <span class="bc-current">{{ project.character }}</span>
      </div>
      <div class="tb-actions">
        <button class="tb-btn" @click="resetLayout">{{ t('projectCanvas.resetLayout') }}</button>
        <button class="tb-btn" :disabled="exporting" @click="doExport">
          {{ exporting ? t('projectCanvas.exporting') : t('projectCanvas.exportProject') }}
        </button>
      </div>
    </div>

    <!-- Docking canvas — mousemove here handles drag tracking -->
    <div class="canvas" @mousemove="onCanvasMouseMove">
      <DockLayout
        :node="layout"
        :dragging="dragging"
        :hoverInfo="hoverInfo"
        :titles="panelTitles"
        :collapsible="['summary', 'settings']"
        :collapsed="collapsed"
        :collapse-dir="null"
        @panel-mousedown="startDrag"
        @move="handleMove"
        @toggle-collapse="toggleCollapse"
      >

        <!-- ① 拍摄计划 -->
        <template #shots>
          <div class="p-inner shots-panel">
            <!-- Panel toolbar -->
            <div class="shots-toolbar">
              <span class="shots-count">{{ shots.length }} {{ t('projectCanvas.shotCountSuffix') }}</span>
              <div class="view-toggle">
                <button class="vt-btn" :class="{ active: viewMode === 'grid' }" :title="t('projectCanvas.gridView')" @click="viewMode = 'grid'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="0" y="0" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="8" y="0" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="0" y="8" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="8" y="8" width="6" height="6" rx="1" fill="currentColor"/>
                  </svg>
                </button>
                <button class="vt-btn" :class="{ active: viewMode === 'list' }" :title="t('projectCanvas.listView')" @click="viewMode = 'list'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="0" y="1" width="14" height="2.5" rx="1" fill="currentColor"/>
                    <rect x="0" y="5.75" width="14" height="2.5" rx="1" fill="currentColor"/>
                    <rect x="0" y="10.5" width="14" height="2.5" rx="1" fill="currentColor"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- Grid view -->
            <div v-if="viewMode === 'grid'" class="shots-grid">
              <div
                v-for="shot in shots"
                :key="shot.shot_id"
                class="shot-card"
                :class="{ 'shot-card-no-thumb': !shot.image_url, 'shot-card-refined': shot.status === 'refined' }"
                @click="navigateTo(`/projects/${projectId}/shots/${shot.shot_id}`)"
              >
                <div v-if="shot.image_url" class="sc-thumb-wrap">
                  <img :src="BASE_URL + shot.image_url" class="sc-thumb" :alt="shot.title" />
                  <div v-if="shot.status === 'refined'" class="sc-refined-overlay">✓ {{ t('projectCanvas.refined') }}</div>
                </div>
                <div class="sc-mood">{{ shot.mood }}</div>
                <div class="sc-title">{{ shot.title }}</div>
                <div class="sc-desc" v-if="shot.description">{{ shot.description }}</div>
                <div class="sc-footer">
                  <span v-if="shot.status === 'error'" class="sc-error-dot" :title="t('projectCanvas.genError')">!</span>
                  <span v-else class="sc-spacer" />
                  <button class="sc-del" @click.stop="removeShot(shot.shot_id)" :title="t('projectCanvas.delete')">✕</button>
                </div>
              </div>
              <div class="shot-add" :class="{ adding: shotAdding }" @click="quickAddShot">
                <span class="add-icon">{{ shotAdding ? '…' : '+' }}</span>
                <span class="add-text">{{ t('projectCanvas.addShot') }}</span>
              </div>
            </div>

            <!-- List view -->
            <div v-else class="shots-list">
              <div
                v-for="shot in shots"
                :key="shot.shot_id"
                class="sl-row"
                :class="{ 'sl-refined': shot.status === 'refined' }"
                @click="navigateTo(`/projects/${projectId}/shots/${shot.shot_id}`)"
              >
                <div class="sl-thumb-wrap">
                  <img v-if="shot.image_url" :src="BASE_URL + shot.image_url" class="sl-thumb" :alt="shot.title" />
                  <div v-else class="sl-thumb-empty">—</div>
                </div>
                <div class="sl-info">
                  <span class="sl-title">{{ shot.title }}</span>
                  <span v-if="shot.mood" class="sl-mood">{{ shot.mood }}</span>
                </div>
                <div class="sl-right">
                  <span v-if="shot.status === 'refined'" class="sl-badge-refined">{{ t('projectCanvas.refined') }}</span>
                  <span v-else-if="shot.status === 'error'" class="sl-badge-error">{{ t('projectCanvas.errorBadge') }}</span>
                  <button class="sc-del" @click.stop="removeShot(shot.shot_id)" :title="t('projectCanvas.delete')">✕</button>
                </div>
              </div>
              <button class="sl-add" :disabled="shotAdding" @click="quickAddShot">
                {{ shotAdding ? '…' : '+ ' + t('projectCanvas.addShot') }}
              </button>
            </div>
          </div>
        </template>

        <!-- ② 拍摄总结 -->
        <template #summary>
          <div class="p-inner plan-panel">
            <!-- 项目概览:计划元信息(主题/日期/视觉方向),卡片式 -->
            <div class="plan-card">
              <div class="pc-head"><span class="pc-title">{{ t('projectCanvas.overview') }}</span></div>
              <div class="pc-rows">
                <!-- 常驻可编辑输入(改完即存到后端 plan) -->
                <div class="po-row">
                  <span class="po-label">{{ t('projectCanvas.theme') }}</span>
                  <input v-model="draft.theme" class="po-input" :placeholder="t('projectCanvas.themePlaceholder')" @change="persistPlan" />
                </div>
                <div class="po-row">
                  <span class="po-label">{{ t('projectCanvas.shootDate') }}</span>
                  <input v-model="draft.shootDate" class="po-input" :placeholder="t('projectCanvas.shootDatePlaceholder')" @change="persistPlan" />
                </div>
                <div class="po-row">
                  <span class="po-label">{{ t('projectCanvas.crew') }}</span>
                  <span class="po-val" :class="{ ph: !crewText }">{{ crewText || t('projectCanvas.crewTodo') }}</span>
                </div>
              </div>
            </div>

            <!-- 连体式标签页:4 指标方块当标签,选中项与下方内容区无缝相连 -->
            <div class="plan-tabs">
              <div class="plan-tiles">
                <button
                  v-for="t in planTiles"
                  :key="t.id"
                  class="plan-tile"
                  :class="{ active: summaryTab === t.id }"
                  @click="summaryTab = t.id"
                >
                  <span class="pt-label"><component :is="t.icon" class="pt-ico" />{{ t.label }}</span>
                  <span v-if="t.ph" class="pt-metric ph">{{ t.ph }}</span>
                  <span v-else class="pt-metric"><span class="pt-num">{{ t.num }}</span><span class="pt-unit">{{ t.unit }}</span></span>
                  <span class="pt-sub" :title="t.sub">{{ t.sub || ' ' }}</span>
                </button>
              </div>

              <!-- 细节区:显示当前选中方块的内容 -->
              <div class="plan-detail">
              <!-- 内容区头部:图标 + 标题 + 说明(四块统一) -->
              <div class="detail-header">
                <span class="dh-icon"><component :is="detailHeader.icon" /></span>
                <div class="dh-text">
                  <span class="dh-title">{{ detailHeader.title }}</span>
                  <span class="dh-desc">{{ detailHeader.desc }}</span>
                </div>
              </div>

              <template v-if="summaryTab === 'equipment'">
                <div class="equip">
                  <template v-if="equipmentList.length">

                    <!-- 准备进度条:勾选项 / 总数 -->
                    <div class="prep-bar">
                      <span class="pb-head"><CircleCheck class="pb-ico" /> {{ t('projectCanvas.preparedProgress', { done: preparedCount, total: equipmentList.length }) }}</span>
                      <div class="pb-track"><div class="pb-fill" :style="{ width: preparedPct + '%' }" /></div>
                      <span class="pb-pct">{{ preparedPct }}%</span>
                    </div>

                    <div v-for="grp in equipGroups" :key="grp.cls" class="equip-group">
                        <div class="equip-group-head"><span class="egh-dot" :class="grp.cls" />{{ grp.label }} <span class="egh-count">{{ grp.items.length }} {{ t('projectCanvas.countSuffix') }}</span></div>
                        <div
                          v-for="e in grp.items"
                          :key="e.name"
                          class="equip-item"
                          :class="{ 'is-ready': isPrepared(e) }"
                        >
                          <button class="ei-check" :class="{ on: isPrepared(e) }" @click="togglePrepared(e)">
                            <Check v-if="isPrepared(e)" class="ei-check-ico" />
                          </button>
                          <span class="ei-icon"><component :is="equipIcon(e.category)" /></span>
                          <div class="ei-body">
                            <span class="ei-name">{{ e.name }}</span>
                            <span v-if="e.desc" class="ei-desc">{{ e.desc }}</span>
                          </div>
                          <span class="ei-status" :class="isPrepared(e) ? 'ready' : 'pending'">
                            <component :is="isPrepared(e) ? CircleCheck : Clock" class="eis-ico" />{{ isPrepared(e) ? t('projectCanvas.prepared') : t('projectCanvas.pending') }}
                          </span>
                          <button
                            class="ei-del"
                            :class="{ armed: pendingDelete === e }"
                            :title="pendingDelete === e ? t('projectCanvas.confirmDelete') : t('projectCanvas.delete')"
                            @click="armDelete(e, () => removeEquipment(e))"
                          >
                            <template v-if="pendingDelete === e">{{ t('projectCanvas.delete') }}</template>
                            <X v-else />
                          </button>
                        </div>
                    </div>
                  </template>
                  <p v-else class="detail-empty">{{ t('projectCanvas.emptyEquip') }}</p>

                  <!-- 添加设备:表单入口 -->
                  <button v-if="!showAddEquip" class="equip-add-btn" @click="showAddEquip = true">{{ t('projectCanvas.addEquip') }}</button>
                  <div v-else class="equip-form">
                    <select v-model="newEquip.category" class="ef-select">
                      <option v-for="c in EQUIP_CATEGORIES" :key="c.key" :value="c.key">{{ c.label }}</option>
                    </select>
                    <input v-model="newEquip.name" class="ef-input" :placeholder="t('projectCanvas.equipNamePlaceholder')" @keydown.enter="submitAddEquip" />
                    <input v-model="newEquip.desc" class="ef-input" :placeholder="t('projectCanvas.equipDescPlaceholder')" @keydown.enter="submitAddEquip" />
                    <label class="ef-req"><input type="checkbox" v-model="newEquip.required" /> {{ t('projectCanvas.requiredEquip') }}</label>
                    <div class="ef-actions">
                      <button class="ef-cancel" @click="showAddEquip = false">{{ t('projectCanvas.cancel') }}</button>
                      <button class="ef-submit" :disabled="!newEquip.name.trim()" @click="submitAddEquip">{{ t('projectCanvas.add') }}</button>
                    </div>
                  </div>
                </div>
              </template>

              <template v-else-if="summaryTab === 'locations'">
                <div v-if="locationCards.length" class="loc-list">
                  <div v-for="(loc, i) in locationCards" :key="i" class="loc-card">
                    <div class="loc-body">
                      <div class="loc-line1">
                        <span class="loc-name">{{ loc.scene }}</span>
                        <span class="loc-type">{{ sceneType(loc.scene) }}</span>
                      </div>
                      <div class="loc-meta">
                        <span v-if="loc.times.length" class="loc-mrow"><Clock class="loc-mi" />{{ loc.times.join('、') }}</span>
                        <span class="loc-mrow"><Clapperboard class="loc-mi" />{{ shotLabels(loc.shotIds) || t('projectCanvas.linkShotsTodo') }}</span>
                        <span v-if="loc.lights.length" class="loc-mrow"><Sun class="loc-mi" />{{ loc.lights.join('、') }}</span>
                      </div>
                      <div class="loc-field">
                        <MapPin class="loc-fi" />
                        <input v-model="locAddr[loc.scene]" class="loc-input" :placeholder="t('projectCanvas.addressPlaceholder')" @change="persistPlan" />
                      </div>
                    </div>
                  </div>
                </div>
                <p v-else class="detail-empty">{{ t('projectCanvas.emptyLoc') }}</p>
              </template>

              <template v-else-if="summaryTab === 'schedule'">
                <div v-if="plan.schedule.length" class="sched">
                  <!-- 总结统计:段数 / 时长 / 场地 / 必拍 -->
                  <div class="sched-stats">
                    <div v-for="(st, i) in schedStats" :key="i" class="ss-tile">
                      <span class="ss-metric"><span v-if="st.pre" class="ss-pre">{{ st.pre }}</span><span class="ss-num">{{ st.num }}</span><span v-if="st.unit" class="ss-unit">{{ st.unit }}</span></span>
                      <span class="ss-sub">{{ st.sub }}</span>
                    </div>
                  </div>

                  <div
                    ref="schedScroll"
                    class="sched-track"
                    @scroll="onSchedScroll"
                    @pointerdown="schedDown"
                    @pointermove="schedMove"
                    @pointerup="schedUp"
                    @pointerleave="schedUp"
                  >
                    <div v-for="(row, i) in plan.schedule" :key="i" class="sched-card">
                      <div class="scd-hd">
                        <span class="scd-num">{{ i + 1 }}</span>
                        <div class="scd-time">
                          <span class="scd-range">{{ row.time }}</span>
                          <span class="scd-dur"><Clock class="scd-i" />{{ row.duration }}</span>
                        </div>
                        <span v-if="row.priority" class="ni-prio" :class="'p-' + row.priority">{{ notePriorityLabel(row.priority) }}</span>
                      </div>

                      <div class="scd-thumb">
                        <template v-if="schedThumbs(row).length">
                          <div
                            v-for="(u, k) in schedThumbs(row).slice(0, 3)"
                            :key="k"
                            class="scd-layer"
                            :style="pileStyle(k, Math.min(schedThumbs(row).length, 3))"
                          >
                            <img :src="u" :alt="row.scene" draggable="false" />
                          </div>
                          <span v-if="schedThumbs(row).length > 1" class="scd-count">{{ t('projectCanvas.thumbCount', { n: schedThumbs(row).length }) }}</span>
                        </template>
                        <span v-else class="scd-ph"><ImageIcon /></span>
                      </div>

                      <div class="scd-info">
                        <div class="scd-row"><MapPin class="scd-ri" /><span class="scd-scene">{{ row.scene }}</span></div>
                        <div class="scd-row"><Clapperboard class="scd-ri" /><span class="scd-k">{{ t('projectCanvas.schedShotLabel') }}</span><span class="scd-v">{{ shotLabels(row.shotIds) || t('projectCanvas.linkTodo') }}</span></div>
                        <div class="scd-row"><FileText class="scd-ri" /><span class="scd-v">{{ row.content }}</span></div>
                        <div v-if="row.light" class="scd-row"><Sun class="scd-ri" /><span class="scd-v">{{ row.light }}</span></div>
                      </div>
                    </div>
                  </div>

                  <div v-if="plan.schedule.length > 1" class="sched-dots">
                    <span class="sd-count">{{ schedActive + 1 }}/{{ plan.schedule.length }}</span>
                    <button
                      v-for="(row, i) in plan.schedule"
                      :key="i"
                      class="sd-dot"
                      :class="{ on: schedActive === i }"
                      :aria-label="t('projectCanvas.segmentAria', { i: i + 1 })"
                      @click="schedGo(i)"
                    />
                  </div>

                  <div v-if="plan.schedule.length > 1" class="sched-hint">
                    <Lightbulb class="sh-ico" /><span>{{ t('projectCanvas.schedHint') }}</span>
                  </div>
                </div>
                <p v-else class="detail-empty">{{ t('projectCanvas.emptySched') }}</p>
              </template>

              <template v-else-if="summaryTab === 'notes'">
                <div class="equip">
                  <template v-if="notesList.length">
                    <!-- 确认进度条 -->
                    <div class="prep-bar">
                      <span class="pb-head"><CircleCheck class="pb-ico" /> {{ t('projectCanvas.confirmedProgress', { done: noteDoneCount, total: notesList.length }) }}</span>
                      <div class="pb-track"><div class="pb-fill" :style="{ width: notePct + '%' }" /></div>
                      <span class="pb-pct">{{ notePct }}%</span>
                    </div>

                    <div v-for="grp in noteGroups" :key="grp.key" class="equip-group">
                      <div class="equip-group-head"><span class="egh-dot req" />{{ grp.label }} <span class="egh-count">{{ grp.items.length }} {{ t('projectCanvas.countSuffix') }}</span></div>
                      <div
                        v-for="n in grp.items"
                        :key="n.title"
                        class="note-item"
                        :class="{ 'is-ready': isNoteDone(n) }"
                      >
                        <button class="ei-check" :class="{ on: isNoteDone(n) }" @click="toggleNoteDone(n)">
                          <Check v-if="isNoteDone(n)" class="ei-check-ico" />
                        </button>
                        <div class="ni-body">
                          <div class="ni-line1">
                            <span class="ni-title">{{ n.title }}</span>
                            <button
                              class="ei-del"
                              :class="{ armed: pendingDelete === n }"
                              :title="pendingDelete === n ? t('projectCanvas.confirmDelete') : t('projectCanvas.delete')"
                              @click="armDelete(n, () => removeNote(n))"
                            >
                              <template v-if="pendingDelete === n">{{ t('projectCanvas.delete') }}</template>
                              <X v-else />
                            </button>
                          </div>
                          <span v-if="n.desc" class="ni-desc">{{ n.desc }}</span>
                          <div class="ni-meta">
                            <span class="ei-status" :class="isNoteDone(n) ? 'ready' : 'pending'">
                              <component :is="isNoteDone(n) ? CircleCheck : Clock" class="eis-ico" />{{ isNoteDone(n) ? t('projectCanvas.confirmed') : t('projectCanvas.pending') }}
                            </span>
                            <span class="ni-prio" :class="'p-' + n.priority">{{ notePriorityLabel(n.priority) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>
                  <p v-else class="detail-empty">{{ t('projectCanvas.emptyNotes') }}</p>

                  <!-- 添加注意事项 -->
                  <button v-if="!showAddNote" class="equip-add-btn" @click="showAddNote = true">{{ t('projectCanvas.addNote') }}</button>
                  <div v-else class="equip-form">
                    <input v-model="newNote.title" class="ef-input" :placeholder="t('projectCanvas.noteTitlePlaceholder')" @keydown.enter="submitAddNote" />
                    <input v-model="newNote.desc" class="ef-input" :placeholder="t('projectCanvas.noteDescPlaceholder')" @keydown.enter="submitAddNote" />
                    <div class="ef-row2">
                      <select v-model="newNote.phase" class="ef-select">
                        <option v-for="p in NOTE_PHASES" :key="p.key" :value="p.key">{{ p.label }}</option>
                      </select>
                      <select v-model="newNote.priority" class="ef-select">
                        <option v-for="p in NOTE_PRIORITIES" :key="p.key" :value="p.key">{{ p.label }}</option>
                      </select>
                    </div>
                    <div class="ef-actions">
                      <button class="ef-cancel" @click="showAddNote = false">{{ t('projectCanvas.cancel') }}</button>
                      <button class="ef-submit" :disabled="!newNote.title.trim()" @click="submitAddNote">{{ t('projectCanvas.add') }}</button>
                    </div>
                  </div>
                </div>
              </template>
              </div>
            </div>
          </div>
        </template>

        <!-- ③ 设定面板 -->
        <template #settings>
          <div class="p-inner">

            <!-- 背景设定(作品/游戏/影视等世界观,通用叫法)—— 默认折叠 -->
            <div class="setting-block">
              <div class="s-section">{{ t('projectCanvas.sectionBackground') }}</div>

              <!-- 封面 + 名称(展开按钮在作品名右边);展开再露简介与信息盒 -->
              <div class="ws-hero">
                <div class="ws-cover" :class="{ empty: !coverUrl }">
                  <img v-if="coverUrl" :src="coverUrl" :alt="project.work" />
                  <div v-else class="ws-cover-ph">
                    <RefreshCw v-if="coverLoading" class="spin" />
                    <ImageIcon v-else />
                  </div>
                  <!-- 首次自动抓;之后「换封面」= 用户自己上传 -->
                  <label class="ws-cover-btn" :class="{ disabled: coverLoading }" :title="coverLoading ? t('projectCanvas.coverAutoGrabbing') : t('projectCanvas.coverUploadOwn')">
                    <input type="file" accept="image/*" hidden :disabled="coverLoading" @change="onUploadCover" />
                    <RefreshCw v-if="coverLoading" class="spin" /><Upload v-else />
                    <span>{{ coverLoading ? t('projectCanvas.grabbingCover') : t('projectCanvas.changeCover') }}</span>
                  </label>
                </div>
                <button class="ws-title-row" @click="bgOpen = !bgOpen">
                  <span class="ws-hero-title">{{ project.work }}</span>
                  <ChevronDown class="s-chev" :class="{ open: bgOpen }" />
                </button>
                <p v-if="bgOpen && worldSetting?.synopsis" class="ws-hero-sub">{{ worldSetting.synopsis }}</p>
              </div>

              <!-- 展开才显示的信息盒:类型 / 时代·地点 / 氛围 / 核心主题 / 标志场景 -->
              <div v-if="worldSetting" v-show="bgOpen" class="ws-info">
                <div class="ws-irow"><Tag class="ws-ii" /><span class="ws-ik">{{ t('projectCanvas.fieldGenre') }}</span><span class="ws-iv">{{ worldSetting.genre ?? '—' }}</span></div>
                <div class="ws-irow"><Clock class="ws-ii" /><span class="ws-ik">{{ t('projectCanvas.fieldEraPlace') }}</span><span class="ws-iv">{{ worldSetting.timeline || worldSetting.era || '—' }}</span></div>
                <div class="ws-irow"><Sparkles class="ws-ii" /><span class="ws-ik">{{ t('projectCanvas.fieldAtmosphere') }}</span><span class="ws-iv">{{ [worldSetting.tone?.visual, worldSetting.tone?.emotion].filter(Boolean).join(' · ') || '—' }}</span></div>
                <div v-if="worldSetting.themes?.length" class="ws-irow">
                  <Star class="ws-ii" /><span class="ws-ik">{{ t('projectCanvas.fieldThemes') }}</span>
                  <span class="ws-iv">{{ worldSetting.themes.join(' · ') }}</span>
                </div>
                <div v-if="worldSetting.iconic_settings?.length" class="ws-irow">
                  <MapPin class="ws-ii" /><span class="ws-ik">{{ t('projectCanvas.fieldIconic') }}</span>
                  <span class="ws-iv">{{ worldSetting.iconic_settings.join(' · ') }}</span>
                </div>
              </div>
            </div>

            <!-- 人物设定:头像选择 + 每角色三段导航(设定 / 服装道具 / 名场面) -->
            <div class="setting-block">
              <div class="s-section">{{ t('projectCanvas.sectionCharacter') }}</div>

              <!-- 角色头像选择器 -->
              <div class="char-picker">
                <button
                  v-for="c in characters" :key="c.id"
                  class="char-ava" :class="{ on: c.id === selectedCharId }"
                  @click="c.id === selectedCharId ? openAvatarEditor(c) : (selectedCharId = c.id)"
                >
                  <span class="ca-img">
                    <img v-if="charAvatar(c)" :src="charAvatar(c)" :alt="c.name" />
                    <span v-else class="ca-ph">{{ (c.name || '?').slice(0, 1) }}</span>
                    <span v-if="c.id === selectedCharId" class="ca-edit"><Pencil /></span>
                  </span>
                  <span class="ca-name">{{ c.name || t('projectCanvas.fieldCharacter') }}</span>
                </button>
                <button class="char-ava add" :title="t('projectCanvas.addCharacterTitle')" @click="addCharacter">
                  <span class="ca-img add"><Plus /></span>
                  <span class="ca-name">{{ t('projectCanvas.addCharacterShort') }}</span>
                </button>
              </div>

              <!-- 三段标签导航 -->
              <div class="char-tabs">
                <button
                  v-for="tb in charTabs" :key="tb.id"
                  class="char-tab" :class="{ on: charTab === tb.id }"
                  @click="charTab = tb.id"
                ><component :is="tb.icon" class="ct-ico" />{{ tb.label }}</button>
              </div>

              <!-- ① 设定:基本信息 + 外貌特征 + 参考图 -->
              <div v-if="charTab === 'setting'" class="char-panel">
                <div class="cp-sub">{{ t('projectCanvas.subBaseInfo') }}</div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldCharacter') }}</span><span class="s-val">{{ selectedChar?.name || '—' }} · {{ project.work }}</span></div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldRole') }}</span><span class="s-val">{{ charBg?.role ?? '—' }}</span></div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldAge') }}</span><span class="s-val">{{ charBg?.age ?? '—' }}</span></div>
                <div v-if="charBg?.backstory" class="s-row s-row-top">
                  <span class="s-key">{{ t('projectCanvas.fieldBackstory') }}</span>
                  <span class="s-val">{{ charBg.backstory }}</span>
                </div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldSurface') }}</span><span class="s-val">{{ charBg?.personality?.surface ?? '—' }}</span></div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldInner') }}</span><span class="s-val">{{ charBg?.personality?.inner ?? '—' }}</span></div>
                <div class="s-row"><span class="s-key">{{ t('projectCanvas.fieldDesire') }}</span><span class="s-val">{{ charBg?.personality?.core_desire ?? '—' }}</span></div>

                <template v-if="visualSpecFields.length">
                  <div class="cp-sub">{{ t('projectCanvas.sectionAppearance') }}</div>
                  <div v-for="f in visualSpecFields" :key="f.label" class="s-row s-row-top">
                    <span class="s-key">{{ f.label }}</span>
                    <div v-if="parseColors(f.value).length" class="swatches">
                      <span
                        v-for="(c, i) in parseColors(f.value)" :key="i"
                        class="swatch" :style="{ background: c.hex }" :title="`${c.name} ${c.hex}`"
                      />
                    </div>
                    <span v-else class="s-val">{{ f.value }}</span>
                  </div>
                </template>

                <template v-if="relations.length">
                  <div class="cp-sub">{{ t('projectCanvas.secRelations') }}</div>
                  <div class="rel-list">
                    <div v-for="(r, i) in relations" :key="i" class="rel-item">
                      <span class="rel-name">{{ r.name }}</span>
                      <span class="rel-rel">{{ r.relationship }}</span>
                    </div>
                  </div>
                </template>

                <div class="cp-sub">{{ t('projectCanvas.sectionRefs') }}</div>
                <div class="refs-mini-grid">
                  <img
                    v-for="(url, i) in allRefUrls" :key="i"
                    :src="url" class="ref-mini-img"
                    :class="{ 'ref-extra': i >= refUrls.length }"
                    :title="i >= refUrls.length ? t('projectCanvas.refExtra') : t('projectCanvas.refOriginal')"
                    :alt="t('projectCanvas.refAlt', { i: i + 1 })"
                    @click="openLightbox(i)"
                  />
                  <label class="ref-add-card">
                    <input type="file" accept="image/*" multiple hidden @change="onAddRefs" />
                    <span class="ref-add-plus">+</span>
                  </label>
                </div>
              </div>

              <!-- ② 服装 · 道具:假发/上衣/…/道具 都是并列的可折叠分组卡片 -->
              <div v-else-if="charTab === 'wardrobe'" class="char-panel wd">
                <div class="wd-head">
                  <span class="wd-badge">{{ t('projectCanvas.wdTotal', { n: wardrobeTotal }) }}</span>
                </div>

                <div v-for="g in wardrobeGroups" :key="g.key" class="wd-group">
                  <button class="wd-cat" @click="toggleCat(g.key)">
                    <span class="wd-cat-ico" :style="{ background: `color-mix(in srgb, ${catStyle(g.key).hue} 16%, transparent)`, color: catStyle(g.key).hue }">
                      <component :is="catStyle(g.key).icon" />
                    </span>
                    <div class="wd-cat-body">
                      <span class="wd-cat-line1"><span class="wd-cat-name">{{ g.label }}</span><span class="wd-cat-count">{{ g.items.length }}</span></span>
                      <span class="wd-cat-preview">{{ groupPreview(g.items) }}</span>
                    </div>
                    <ChevronDown class="wd-gh-chev" :class="{ open: openCats[g.key] }" />
                  </button>
                  <div v-show="openCats[g.key]" v-for="it in g.items" :key="it.id" class="wd-card">
                    <span class="wd-thumb">
                      <img v-if="itemImg(it)" :src="itemImg(it)" :alt="it.name" />
                      <component v-else :is="catStyle(g.key).icon" class="wd-thumb-ph" />
                    </span>
                    <div class="wd-body">
                      <span class="wd-name">{{ it.name }}</span>
                      <span v-if="it.note" class="wd-note">{{ it.note }}</span>
                    </div>
                    <span class="wd-pill" :class="it.essential === false ? 'backup' : 'ess'">
                      {{ it.essential === false ? t('projectCanvas.wdBackup') : t('projectCanvas.wdEssential') }}
                    </span>
                    <div class="wd-menu-wrap">
                      <button class="wd-kebab" @click.stop="toggleItemMenu(it.id)"><MoreVertical /></button>
                      <div v-if="openItemMenu === it.id" class="wd-menu" @click.stop>
                        <label class="wd-mi">
                          <input type="file" accept="image/*" hidden @change="e => onUploadItemImage(e, it)" />
                          <Upload /><span>{{ t('projectCanvas.wdMenuUpload') }}</span>
                        </label>
                        <button class="wd-mi" @click="toggleEssential(it)">
                          <Star /><span>{{ it.essential === false ? t('projectCanvas.wdMenuSetEssential') : t('projectCanvas.wdMenuSetBackup') }}</span>
                        </button>
                        <button class="wd-mi danger" @click="removeItem(it); openItemMenu = null"><X /><span>{{ t('projectCanvas.delete') }}</span></button>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-if="!costumeList.length && !propsList.length" class="detail-empty">{{ t('projectCanvas.emptyCostume') }}</p>

                <!-- 添加(服装或道具:分类里选道具即加道具) -->
                <div v-if="showAdd" class="equip-form">
                  <select v-model="newItem.category" class="ef-select">
                    <option v-for="c in ADD_CATEGORIES" :key="c.key" :value="c.key">{{ c.label }}</option>
                  </select>
                  <input v-model="newItem.name" class="ef-input" :placeholder="newItem.category === 'props' ? t('projectCanvas.propNamePlaceholder') : t('projectCanvas.costumeNamePlaceholder')" @keydown.enter="submitAdd" />
                  <input v-model="newItem.note" class="ef-input" :placeholder="t('projectCanvas.notePlaceholder')" @keydown.enter="submitAdd" />
                  <div class="ef-actions">
                    <button class="ef-cancel" @click="showAdd = false">{{ t('projectCanvas.cancel') }}</button>
                    <button class="ef-submit" @click="submitAdd">{{ t('projectCanvas.add') }}</button>
                  </div>
                </div>
                <button v-else class="wd-add-card single" @click="showAdd = true">
                  <span class="wd-add-ico"><Plus /></span><span>{{ t('projectCanvas.add') }}</span>
                </button>
              </div>

              <!-- ③ 名场面:标题 + 大概出处 + 详细描述(设定参考,非拍摄指令)。
                   项目创建后在后台静默生成一次,用户无感;之后可手动增删。 -->
              <div v-else class="char-panel mo">
                <div v-if="momentsList.length" class="mo-list">
                  <div v-for="(m, i) in momentsList" :key="m.id || i" class="mo-card">
                    <div class="mo-head">
                      <span class="mo-num">{{ i + 1 }}</span>
                      <span class="mo-title">{{ m.title }}</span>
                      <button
                        class="ei-del" :class="{ armed: pendingDelete === m }"
                        :title="pendingDelete === m ? t('projectCanvas.confirmDelete') : t('projectCanvas.delete')"
                        @click="armDelete(m, () => removeMoment(m))"
                      >
                        <template v-if="pendingDelete === m">{{ t('projectCanvas.delete') }}</template>
                        <X v-else />
                      </button>
                    </div>
                    <span v-if="m.source" class="mo-source">{{ m.source }}</span>
                    <p v-if="m.description" class="mo-desc">{{ m.description }}</p>
                  </div>
                </div>
                <p v-else-if="!momentsLoading" class="detail-empty">{{ t('projectCanvas.emptyMoments') }}</p>

                <div v-if="showAddMoment" class="equip-form">
                  <input v-model="newMoment.title" class="ef-input" :placeholder="t('projectCanvas.momentTitlePlaceholder')" @keydown.enter="submitAddMoment" />
                  <input v-model="newMoment.source" class="ef-input" :placeholder="t('projectCanvas.momentSourcePlaceholder')" @keydown.enter="submitAddMoment" />
                  <textarea v-model="newMoment.description" class="ef-input mo-ta" :placeholder="t('projectCanvas.momentDescPlaceholder')" rows="3" />
                  <div class="ef-actions">
                    <button class="ef-cancel" @click="showAddMoment = false">{{ t('projectCanvas.cancel') }}</button>
                    <button class="ef-submit" :disabled="!newMoment.title.trim()" @click="submitAddMoment">{{ t('projectCanvas.add') }}</button>
                  </div>
                </div>
                <button v-else class="wd-add-card single" @click="showAddMoment = true">
                  <span class="wd-add-ico"><Plus /></span><span>{{ t('projectCanvas.addMoment') }}</span>
                </button>
              </div>
            </div>

          </div>
        </template>

      </DockLayout>
    </div>

    <!-- Floating AI planning assistant — always-present companion (same pattern
         as the new-project flow). Its replies still drive the 拍摄总结 panel via
         `brief`; only the chat UI moved out of the dock. -->
    <div class="ai-widget" :style="aiDrag.style">
      <!-- expanded (avatar clicked): full conversation + the only input surface -->
      <div v-if="aiExpanded" class="ai-widget-panel">
        <div class="ai-widget-log" ref="aiContainer">
          <div
            v-for="(msg, i) in aiMessages"
            :key="i"
            class="ai-msg"
            :class="msg.role"
          >
            <div v-if="msg.role === 'agent'" class="ai-avatar">AI</div>
            <div class="ai-bubble">
              {{ msg.text }}
              <button
                v-if="msg.retryText"
                class="retry-btn"
                :disabled="aiLoading"
                @click="sendAiMessage(msg.retryText)"
              >{{ t('projectCanvas.retry') }}</button>
            </div>
          </div>
          <div v-if="aiLoading" class="ai-msg agent">
            <div class="ai-avatar">AI</div>
            <div class="ai-bubble typing"><span /><span /><span /></div>
          </div>
        </div>
        <div class="ai-widget-input-row">
          <input
            v-model="aiInput"
            class="ai-input"
            :placeholder="t('projectCanvas.aiPlaceholder')"
            :disabled="aiLoading"
            @keydown.enter.exact="onAiInputEnter"
          />
          <button class="ai-send" :disabled="!aiInput.trim() || aiLoading" @click="sendAiMessage()">↑</button>
        </div>
      </div>

      <!-- collapsed (default): the assistant just speaks — no input surface -->
      <template v-else>
        <div v-if="aiLoading" class="ai-widget-bubble typing"><span /><span /><span /></div>
        <div v-else-if="latestAgentMessage" class="ai-widget-bubble">
          {{ latestAgentMessage.text }}
          <button
            v-if="latestAgentMessage.retryText"
            class="retry-btn"
            :disabled="aiLoading"
            @click="sendAiMessage(latestAgentMessage.retryText)"
          >{{ t('projectCanvas.retry') }}</button>
        </div>
      </template>

      <button
        class="ai-widget-avatar"
        @pointerdown="aiDrag.onPointerDown"
        @click="aiDrag.consumeClick() || (aiExpanded = !aiExpanded)"
      ><span>AI</span></button>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <div v-if="lightboxIndex !== null" class="lightbox" @click.self="lightboxIndex = null">
        <button class="lb-close" @click="lightboxIndex = null">✕</button>
        <button v-if="lightboxIndex > 0" class="lb-arrow lb-prev" @click="lightboxIndex--">‹</button>
        <button v-if="lightboxIndex < allRefUrls.length - 1" class="lb-arrow lb-next" @click="lightboxIndex++">›</button>
        <div class="lb-img-wrap">
          <img :src="allRefUrls[lightboxIndex]" class="lb-img" :alt="t('projectCanvas.refAlt', { i: lightboxIndex + 1 })" />
          <div class="lb-badge" :class="lightboxIndex >= refUrls.length ? 'lb-badge-extra' : 'lb-badge-orig'">
            {{ lightboxIndex >= refUrls.length ? t('projectCanvas.refExtraShort') : t('projectCanvas.refOriginalShort') }}
          </div>
        </div>
        <div class="lb-counter">{{ lightboxIndex + 1 }} / {{ allRefUrls.length }}</div>
      </div>
    </Teleport>

    <Transition name="toast-fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>

    <AvatarEditor
      v-if="avatarEditFor"
      :project-id="projectId"
      :character="avatarEditFor"
      @close="avatarEditFor = null"
      @saved="onAvatarSaved"
    />

  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, reactive, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  MapPin, Clock, TriangleAlert, Package, Check, CircleCheck, X, Sun, Clapperboard, FileText,
  Camera, Aperture, Lightbulb, Disc, BatteryFull, Plug, Mic, Image as ImageIcon, Wrench, Shirt,
  Tag, Sparkles, Star, RefreshCw, Upload, ChevronDown, User, Plus, Pencil, MoreVertical,
  Scissors, Gem, Footprints,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import TripodIcon from '~/components/equip-icons/TripodIcon.vue'
import AvatarEditor from '~/components/AvatarEditor.vue'

// 设备分类 → 图标(线描,跟随主题色)。support 用用户提供的三脚架矢量,其余 Lucide。
const EQUIP_ICONS: Record<string, Component> = {
  camera:    Camera,       // 相机机身
  lens:      Aperture,     // 镜头
  light:     Lightbulb,    // 灯光
  reflector: Disc,         // 反光/柔光板
  support:   TripodIcon,   // 支撑(三脚架)—— 用户提供的矢量图标
  power:     BatteryFull,  // 电池
  charger:   Plug,         // 充电
  audio:     Mic,          // 收音
  backdrop:  ImageIcon,    // 背景
  misc:      Wrench,       // 杂项/工具
}
const equipIcon = (cat?: string) => (cat && EQUIP_ICONS[cat]) || Package
import type { LayoutNode, PanelId, Edge } from '~/components/DockLayout.vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const route = useRoute()
const api = useApi()
const { t } = useLocale()

// ── Project data ──────────────────────────────────────────
const projectData = ref<any>(null)

const projectId = computed(() =>
  Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
)

const project = computed(() => ({
  work:      projectData.value?.series    ?? '—',
  character: projectData.value?.character ?? '—',
}))

const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

const refUrls = computed<string[]>(() =>
  (projectData.value?.refs ?? []).map((r: string) => BASE_URL + r)
)
const extraRefUrls = computed<string[]>(() =>
  (projectData.value?.extra_refs ?? []).map((r: string) => BASE_URL + r)
)
const allRefUrls = computed<string[]>(() => [...refUrls.value, ...extraRefUrls.value])

// ── Lightbox ──────────────────────────────────────────────
const lightboxIndex = ref<number | null>(null)
function openLightbox(i: number) { lightboxIndex.value = i }

// Keyboard navigation
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e) => {
    if (lightboxIndex.value === null) return
    if (e.key === 'Escape') lightboxIndex.value = null
    if (e.key === 'ArrowLeft' && lightboxIndex.value > 0) lightboxIndex.value--
    if (e.key === 'ArrowRight' && lightboxIndex.value < allRefUrls.value.length - 1) lightboxIndex.value++
  })
}

// ── Extra refs upload ─────────────────────────────────────
async function onAddRefs(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files?.length) return
  const uploads = Array.from(files).map(f => api.addExtraRef(projectId.value, f))
  const results = await Promise.all(uploads)
  if (!projectData.value) return
  const newUrls = results.map(r => BASE_URL + r.url)
  projectData.value.extra_refs = [...(projectData.value.extra_refs ?? []), ...results.map(r => r.url)]
  // Reset input so same file can be re-selected
  ;(e.target as HTMLInputElement).value = ''
}

const worldSetting = computed(() => projectData.value?.world?.worldSetting ?? null)

// ── Characters (id-based list; single primary for now) ──────────────────────
// 人物设定 / 外貌特征 are scoped to the selected character. 背景设定 (world) stays
// project-level (shared). Adding a 2nd character is 阶段 2 (coming soon).
const characters = computed<any[]>(() => projectData.value?.characters ?? [])
const selectedCharId = ref<string>('')
const selectedChar = computed(() =>
  characters.value.find(c => c.id === selectedCharId.value) || characters.value[0] || null)
watch(characters, (list) => {
  if (list.length && !list.some(c => c.id === selectedCharId.value)) selectedCharId.value = list[0].id
}, { immediate: true })

const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2600)
}
function addCharacter() { showToast(t('projectCanvas.addCharacterComingSoon')) }

// Per-character 3-tab navigator: 设定 (base + appearance + refs) / 服装道具 / 名场面.
type CharTab = 'setting' | 'wardrobe' | 'moments'
const charTab = ref<CharTab>('setting')
const charTabs = computed<{ id: CharTab; label: string; icon: any }[]>(() => [
  { id: 'setting',  label: t('projectCanvas.charTabSetting'),  icon: User },
  { id: 'wardrobe', label: t('projectCanvas.charTabWardrobe'), icon: Shirt },
  { id: 'moments',  label: t('projectCanvas.charTabMoments'),  icon: Star },
])
// Avatar = the character's own cropped avatar if set, else its first reference
// image (project-level refs for now; future characters get their own).
function charAvatar(c: any): string {
  if (c?.avatar) return BASE_URL + c.avatar
  return allRefUrls.value[0] || ''
}

// Avatar editor overlay (click a character avatar to upload + crop).
const avatarEditFor = ref<any>(null)
function openAvatarEditor(c: any) { avatarEditFor.value = c }
function onAvatarSaved(url: string) {
  const c = characters.value.find((x: any) => x.id === avatarEditFor.value?.id)
  if (c) c.avatar = url   // cache-busted url from backend
}

const charBg = computed(() => selectedChar.value?.character_data?.characterBackground ?? null)

// 人物关系: [{ name, relationship, importance }]
const relations = computed<any[]>(() => {
  const r = charBg.value?.relations
  return Array.isArray(r) ? r.filter(x => x?.name) : []
})

// 配色 field → color swatches. Parses "名称（#HEX）、名称（#HEX）" into { name, hex }.
function parseColors(v?: string): { name: string; hex: string }[] {
  if (!v) return []
  const out: { name: string; hex: string }[] = []
  const re = /([^、,（(]+)\s*[（(]\s*(#[0-9A-Fa-f]{3,8})\s*[）)]/g
  let m: RegExpExecArray | null
  while ((m = re.exec(v))) out.push({ name: m[1].trim(), hex: m[2] })
  return out
}

// ── 名场面 (signature scenes) — character canon, LLM-generated + editable ──────
// { title, source (rough), description } — reference for shots + the user, no
// shoot tips (this is 设定). Stored per character; regeneratable.
interface MomentItem { id?: string; title: string; source?: string; description?: string }
const momentsList = ref<MomentItem[]>([])
const momentsLoading = ref(false)
function loadMoments() {
  momentsList.value = (selectedChar.value?.moments ?? []).map((m: any) => ({ ...m }))
}
// Resolved id (selectedCharId may lag on first load; selectedChar falls back to
// the primary character, so use its id for API calls).
const activeCharId = computed(() => selectedChar.value?.id || '')
function persistMoments() {
  const cid = activeCharId.value
  if (!cid) return
  if (selectedChar.value) selectedChar.value.moments = momentsList.value.map(m => ({ ...m }))
  api.saveMoments(projectId.value, cid, momentsList.value)
    .catch(e => console.error('Failed to save moments', e))
}
// Generated once per character, silently in the background when the project is
// opened and the character has none — the user never sees a loading step; by the
// time they browse to 名场面 it's already there. Cached forever after.
async function autoGenerateMomentsIfMissing() {
  const cid = activeCharId.value
  if (!cid || momentsList.value.length || momentsLoading.value) return
  momentsLoading.value = true
  try {
    const { moments } = await api.generateMoments(projectId.value, cid)
    if (selectedChar.value) selectedChar.value.moments = moments
    momentsList.value = moments.map((m: any) => ({ ...m }))
  } catch (e) {
    console.error('Failed to generate moments', e)
  } finally {
    momentsLoading.value = false
  }
}
watch(selectedCharId, () => { loadMoments(); autoGenerateMomentsIfMissing() })
function removeMoment(item: MomentItem) {
  const i = momentsList.value.indexOf(item)
  if (i >= 0) momentsList.value.splice(i, 1)
  persistMoments()
}
const showAddMoment = ref(false)
const newMoment = reactive({ title: '', source: '', description: '' })
function submitAddMoment() {
  if (!newMoment.title.trim()) return
  momentsList.value.push({
    title: newMoment.title.trim(),
    source: newMoment.source.trim() || undefined,
    description: newMoment.description.trim() || undefined,
  })
  newMoment.title = ''; newMoment.source = ''; newMoment.description = ''
  showAddMoment.value = false
  persistMoments()
}

// 背景设定 folds collapsed by default (常态) — it's tall; expand to see detail.
const bgOpen = ref(false)

// Work cover (背景设定 hero) — served from context/cover.<ext>.
// Auto-grabbed once (on first open if missing); replaced only by user upload.
const coverUrl = computed(() => projectData.value?.cover ? BASE_URL + projectData.value.cover : '')
const coverLoading = ref(false)   // true while the one-time auto-grab is running

async function autoGrabCoverIfMissing() {
  if (coverUrl.value || coverLoading.value) return
  coverLoading.value = true
  try {
    const { url } = await api.grabCover(projectId.value)
    if (projectData.value) projectData.value.cover = url   // url is cache-busted (mtime)
  } catch (e) {
    console.error('Auto cover grab failed (user can upload one)', e)
  } finally {
    coverLoading.value = false
  }
}

async function onUploadCover(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const { url } = await api.uploadCover(projectId.value, file)
    if (projectData.value) projectData.value.cover = url
  } catch (err) {
    console.error('Failed to upload cover', err)
  } finally {
    input.value = ''   // allow re-selecting the same file
  }
}

const visualSpecFields = computed(() => {
  const vs = selectedChar.value?.visual_spec
  if (!vs) return []
  // Multilang dict {zh,en,ja} or legacy plain-text — always show zh by default
  const spec: string = typeof vs === 'object' ? (vs.zh ?? '') : vs
  return spec.split('\n')
    .filter(Boolean)
    .map(line => {
      const idx = line.indexOf(': ')
      if (idx === -1) return null
      return { label: line.slice(0, idx), value: line.slice(idx + 2) }
    })
    .filter(Boolean) as { label: string; value: string }[]
})

// ── Plan panel (right) — 项目概览 + 4 指标方块(标签)+ 细节区 ──────────────
// UI is built to the agreed field contract; fields the backend/AI don't produce
// yet (theme / shootDate / schedule / notes / equipment.required) read as empty
// and render as 占位. Only the presentation lives here — data is filled later.
type PlanTab = 'equipment' | 'locations' | 'schedule' | 'notes'
const summaryTab = ref<PlanTab>('equipment')

interface EquipmentItem { id?: string; name: string; required?: boolean; desc?: string; category?: string }
interface ScheduleRow { id?: string; time: string; scene: string; shotIds: string[]; content: string; duration: string; light?: string; priority?: NotePriority }
type NotePhase = 'pre' | 'onsite' | 'other'
type NotePriority = 'high' | 'mid' | 'low'
interface NoteItem { id?: string; title: string; desc?: string; phase: NotePhase; priority: NotePriority }

// Plan-panel data comes from the backend: GET /projects/{id} → plan.data, stored
// on disk at plan/plan.json. snake_case on the wire, camelCase in the UI. All
// edits round-trip the whole blob back via PUT /projects/{id}/plan (persistPlan).
const planData = computed<any>(() => projectData.value?.plan?.data ?? {})

function mapScheduleRow(r: any): ScheduleRow {
  return {
    time: r.time ?? '', scene: r.scene ?? '', shotIds: r.shot_ids ?? [],
    content: r.content ?? '', duration: r.duration ?? '', light: r.light, priority: r.priority,
  }
}

const plan = computed(() => {
  const d = planData.value
  const schedule = (d.schedule ?? []).map(mapScheduleRow) as ScheduleRow[]
  // 场地名单派生自日程的去重场景(不单独存储)。
  const locations = [...new Set(schedule.map(r => r.scene).filter(Boolean))]
  return {
    theme:     (d.theme ?? '') as string,
    shootDate:  (d.shoot_date ?? '') as string,
    // 参与人数(制片信息):摄影 / coser / 后勤 各几人
    crew:       (d.crew ?? {}) as { photographers?: number; cosers?: number; logistics?: number },
    locations,
    schedule,
  }
})

// Serialize current UI state → the backend blob (camelCase → snake_case) and
// coarse-save it. schedule/crew have no editing UI yet, so they round-trip
// verbatim from planData. Every mutation calls persistPlan.
function buildPlanData() {
  return {
    theme: draft.theme,
    shoot_date: draft.shootDate,
    crew: planData.value.crew ?? {},
    equipment: equipmentList.value.map(e => ({
      id: e.id, name: e.name, required: e.required, desc: e.desc, category: e.category,
    })),
    schedule: planData.value.schedule ?? [],
    notes: notesList.value.map(n => ({
      id: n.id, title: n.title, desc: n.desc, phase: n.phase, priority: n.priority,
    })),
    location_meta: Object.fromEntries(
      Object.entries(locAddr)
        .filter(([, v]) => (v as string)?.trim())
        .map(([k, v]) => [k, { address: (v as string).trim() }]),
    ),
    prepared: Object.keys(prepared).filter(k => prepared[k]),
    notes_done: Object.keys(noteDone).filter(k => noteDone[k]),
  }
}

let planSaveTimer: ReturnType<typeof setTimeout> | null = null
function persistPlan() {
  if (!projectData.value) return
  const data = buildPlanData()
  // Optimistic local sync so planData-derived computeds don't flash stale.
  if (projectData.value.plan) {
    projectData.value.plan.data = { ...projectData.value.plan.data, ...data }
  }
  if (planSaveTimer) clearTimeout(planSaveTimer)
  planSaveTimer = setTimeout(() => {
    api.savePlanData(projectId.value, data).catch(e => console.error('Failed to save plan', e))
  }, 400)
}

// Re-seed all editable state from planData. Called on load and whenever the AI
// assistant mutates the plan (its chat response carries the fresh plan.data).
// equipmentList / notesList / prepared / noteDone / locAddr / draft are separate
// reactive state (not derived from planData), so they must be re-synced explicitly.
function syncPlanFromData() {
  draft.theme     = plan.value.theme
  draft.shootDate = plan.value.shootDate
  loadEquipment()
  loadPrepared()
  loadNotes()
  loadNoteDone()
  loadLocationMeta()
}

// ── Equipment: editable list (add/remove), persisted to the backend plan blob.
// addEquipment / removeEquipment are the single mutation surface — exposing them
// as AI tools later won't touch any caller. Field shape { category, name, desc,
// required } is exactly the future tool's parameter schema.
const EQUIP_CATEGORIES = computed(() => [
  { key: 'camera',    label: t('projectCanvas.catCamera') },
  { key: 'lens',      label: t('projectCanvas.catLens') },
  { key: 'light',     label: t('projectCanvas.catLight') },
  { key: 'reflector', label: t('projectCanvas.catReflector') },
  { key: 'support',   label: t('projectCanvas.catSupport') },
  { key: 'power',     label: t('projectCanvas.catPower') },
  { key: 'charger',   label: t('projectCanvas.catCharger') },
  { key: 'audio',     label: t('projectCanvas.catAudio') },
  { key: 'backdrop',  label: t('projectCanvas.catBackdrop') },
  { key: 'misc',      label: t('projectCanvas.catMisc') },
])
const equipmentList = ref<EquipmentItem[]>([])
function loadEquipment() {
  equipmentList.value = (planData.value.equipment ?? []).map((e: any) =>
    (typeof e === 'string' ? { name: e } : { ...e }))
}
function addEquipment(item: EquipmentItem) {
  equipmentList.value.push({ ...item })
  persistPlan()
}
function removeEquipment(item: EquipmentItem) {
  const i = equipmentList.value.indexOf(item)
  if (i >= 0) equipmentList.value.splice(i, 1)
  delete prepared[item.name]   // drop its checklist state too
  persistPlan()
}

// Inline two-step delete confirm (no modal — the × arms into a 删除 button that
// must be clicked again; auto-reverts after 3s). Guards against mis-taps.
// Generic over any item object (compared by reference) so equipment + notes
// share one implementation; caller passes the actual remove action.
const pendingDelete = ref<unknown>(null)
let delTimer: ReturnType<typeof setTimeout> | null = null
function armDelete(item: unknown, onConfirm: () => void) {
  if (delTimer) clearTimeout(delTimer)
  if (pendingDelete.value === item) {
    onConfirm()
    pendingDelete.value = null
  } else {
    pendingDelete.value = item
    delTimer = setTimeout(() => { if (pendingDelete.value === item) pendingDelete.value = null }, 3000)
  }
}

// Add-equipment inline form
const showAddEquip = ref(false)
const newEquip = reactive({ category: 'camera', name: '', desc: '', required: true })
function submitAddEquip() {
  if (!newEquip.name.trim()) return
  addEquipment({
    category: newEquip.category,
    name: newEquip.name.trim(),
    desc: newEquip.desc.trim() || undefined,
    required: newEquip.required,
  })
  newEquip.name = ''; newEquip.desc = ''   // keep category/required for quick repeat
  showAddEquip.value = false
}

// Equipment grouped by 必要 / 可选 for the detail list.
const requiredEquip = computed(() => equipmentList.value.filter(e => e.required !== false))
const optionalEquip = computed(() => equipmentList.value.filter(e => e.required === false))
const equipGroups = computed(() => [
  { cls: 'req', label: t('projectCanvas.groupRequired'), items: requiredEquip.value },
  { cls: 'opt', label: t('projectCanvas.groupOptional'), items: optionalEquip.value },
].filter(g => g.items.length))

// ── Notes (注意事项): same editable/confirm/CRUD pattern as equipment, but
// grouped by shoot phase + carries a priority. add/removeNote mirror the future
// AI-tool params { title, desc, phase, priority }.
const NOTE_PHASES = computed<{ key: NotePhase; label: string }[]>(() => [
  { key: 'pre',    label: t('projectCanvas.phasePre') },
  { key: 'onsite', label: t('projectCanvas.phaseOnsite') },
  { key: 'other',  label: t('projectCanvas.phaseOther') },
])
const NOTE_PRIORITIES = computed<{ key: NotePriority; label: string }[]>(() => [
  { key: 'high', label: t('projectCanvas.prioHigh') },
  { key: 'mid',  label: t('projectCanvas.prioMid') },
  { key: 'low',  label: t('projectCanvas.prioLow') },
])
const notePriorityLabel = (p: NotePriority) =>
  p === 'high' ? t('projectCanvas.prioHigh') : p === 'mid' ? t('projectCanvas.prioMid') : t('projectCanvas.prioLow')

const notesList = ref<NoteItem[]>([])
function loadNotes() {
  notesList.value = (planData.value.notes ?? []).map((n: any) => ({ ...n })) as NoteItem[]
}
function addNote(item: NoteItem) { notesList.value.push({ ...item }); persistPlan() }
function removeNote(item: NoteItem) {
  const i = notesList.value.indexOf(item)
  if (i >= 0) notesList.value.splice(i, 1)
  delete noteDone[item.title]
  persistPlan()
}

// confirmed (已确认) checklist state, per project
const noteDone = reactive<Record<string, boolean>>({})
function loadNoteDone() {
  for (const k of Object.keys(noteDone)) delete noteDone[k]
  ;(planData.value.notes_done ?? []).forEach((t: string) => { noteDone[t] = true })
}
function toggleNoteDone(n: NoteItem) {
  noteDone[n.title] = !noteDone[n.title]
  persistPlan()
}
const isNoteDone = (n: NoteItem) => !!noteDone[n.title]
const noteDoneCount = computed(() => notesList.value.filter(n => noteDone[n.title]).length)
const notePct = computed(() => {
  const t = notesList.value.length
  return t ? Math.round((noteDoneCount.value / t) * 100) : 0
})
const noteGroups = computed(() =>
  NOTE_PHASES.value.map(p => ({ ...p, items: notesList.value.filter(n => n.phase === p.key) }))
    .filter(g => g.items.length))

// Add-note inline form
const showAddNote = ref(false)
const newNote = reactive<{ title: string; desc: string; phase: NotePhase; priority: NotePriority }>({
  title: '', desc: '', phase: 'pre', priority: 'mid',
})
function submitAddNote() {
  if (!newNote.title.trim()) return
  addNote({ title: newNote.title.trim(), desc: newNote.desc.trim() || undefined, phase: newNote.phase, priority: newNote.priority })
  newNote.title = ''; newNote.desc = ''   // keep phase/priority for quick repeat
  showAddNote.value = false
}
// "已准备" checklist state — user ticks items as they pack. Persisted as
// plan.prepared (a list of equipment names) in the backend plan blob.
const prepared = reactive<Record<string, boolean>>({})
function loadPrepared() {
  for (const k of Object.keys(prepared)) delete prepared[k]
  ;(planData.value.prepared ?? []).forEach((n: string) => { prepared[n] = true })
}
function togglePrepared(e: EquipmentItem) {
  prepared[e.name] = !prepared[e.name]
  persistPlan()
}
const isPrepared = (e: EquipmentItem) => !!prepared[e.name]
const preparedCount = computed(() => equipmentList.value.filter(e => prepared[e.name]).length)
const preparedPct = computed(() => {
  const t = equipmentList.value.length
  return t ? Math.round((preparedCount.value / t) * 100) : 0
})

// Always-editable overview meta (theme/date). Session-local for now — there's
// no save endpoint for these fields yet; persistence comes with the plan-data layer.
const draft = reactive({ theme: '', shootDate: '' })

// "摄影 2 · Coser 1 · 后勤 3" — only the roles that have a count.
const crewText = computed(() => {
  const c = plan.value.crew
  const parts: string[] = []
  if (c.photographers) parts.push(`${t('projectCanvas.crewPhotographers')} ${c.photographers}`)
  if (c.cosers)        parts.push(`${t('projectCanvas.crewCosers')} ${c.cosers}`)
  if (c.logistics)     parts.push(`${t('projectCanvas.crewLogistics')} ${c.logistics}`)
  return parts.join(' · ')
})

// Sum "40 分钟"-style durations → structured { num, unit } so the tile can
// render the number big and the unit at normal size.
function scheduleTotal(sched: ScheduleRow[]): { pre?: string; num: string; unit: string } | null {
  const mins = sched.reduce((sum, r) => sum + (parseInt(r.duration) || 0), 0)
  if (!mins) return null
  if (mins < 60) return { num: String(mins), unit: t('projectCanvas.unitMinutes') }
  const h = mins / 60
  return { pre: t('projectCanvas.approxPrefix'), num: Number.isInteger(h) ? String(h) : h.toFixed(1), unit: t('projectCanvas.unitHours') }
}

// Map a stored shot_id → display label S01 (by position in the shots list).
function shotLabels(ids: string[]): string {
  return (ids ?? []).map((id) => {
    const idx = shots.value.findIndex((s: any) => s.shot_id === id)
    return idx >= 0 ? `S${String(idx + 1).padStart(2, '0')}` : id
  }).join('、')
}

// ── Schedule carousel: one full-width card per segment, horizontal snap-scroll
// + drag + clickable dots. Cover = the segment's shot images stacked (book-pile).
function schedThumbs(row: ScheduleRow): string[] {
  return (row.shotIds ?? [])
    .map(id => shots.value.find((s: any) => s.shot_id === id))
    .filter((s: any) => s?.image_url)
    .map((s: any) => BASE_URL + s.image_url)
}
// pile layer transform: k=0 is the top card (first shot); later cards tuck to
// the bottom-right so their edges peek out.
function pileStyle(k: number, n: number) {
  return {
    transform: `translate(${k * 6}px, ${k * 6}px)`,
    zIndex: n - k,
    ...(k > 0 ? { filter: `brightness(${Math.max(0.6, 1 - k * 0.12)})` } : {}),
  }
}
// 日程头部小统计:段数 / 总时长 / 场地数 / 必拍(高优段)数
// 场地:按地点聚合的"这里拍什么"视图。当前从 schedule 归组(临时);等 shot
// 加上 location 字段后,数据源改成从 shots 派生即可,此处 UI 不变。
const locationCards = computed(() => {
  const map = new Map<string, { scene: string; shotIds: string[]; segments: number; times: string[]; lights: string[] }>()
  for (const row of plan.value.schedule) {
    const e = map.get(row.scene) ?? { scene: row.scene, shotIds: [], segments: 0, times: [], lights: [] }
    e.shotIds.push(...(row.shotIds ?? []))
    e.segments += 1
    if (row.time) e.times.push(row.time)
    if (row.light && !e.lights.includes(row.light)) e.lights.push(row.light)   // 光线由镜头需要决定,派生自日程
    map.set(row.scene, e)
  }
  // 日程为空时,退回用孤立的 locations 名单当占位
  if (map.size === 0) {
    return plan.value.locations.map(name => ({ scene: name, shotIds: [] as string[], segments: 0, times: [] as string[], lights: [] as string[] }))
  }
  return [...map.values()]
})

// 室内/室外/棚子:根据场景自动判定(不由用户选)。mock 阶段用场景名关键词
// 猜;等 AI 给出 location.type 字段后,把这里换成读那个字段即可。
function sceneType(scene: string): string {
  if (/棚|影棚/.test(scene)) return t('projectCanvas.sceneStudio')
  if (/室外|户外|街|公园|操场|天台|门口|广场|野外|马路|路口/.test(scene)) return t('projectCanvas.sceneOutdoor')
  return t('projectCanvas.sceneIndoor')
}

// 地点唯一的用户元数据:实际地址(系统推不出、只有用户知道)。其余(类型/时间/
// 镜头/光线)全是派生的。按地点名存 plan.location_meta。
const locAddr = reactive<Record<string, string>>({})
function loadLocationMeta() {
  const meta = planData.value.location_meta ?? {}
  for (const name in meta) if (meta[name]?.address) locAddr[name] = meta[name].address
}

const schedStats = computed(() => {
  const s = plan.value.schedule
  const total = scheduleTotal(s)
  const scenes = new Set(s.map(r => r.scene)).size
  const mustShoot = s.filter(r => r.priority === 'high').length
  return [
    { num: String(s.length), unit: t('projectCanvas.unitStage'), sub: t('projectCanvas.statStageSub') },
    total
      ? { pre: total.pre, num: total.num, unit: total.unit, sub: t('projectCanvas.statDurationSub') }
      : { num: '—', unit: '', sub: t('projectCanvas.statDurationSub') },
    { num: String(scenes), unit: t('projectCanvas.unitPlaceCount'), sub: t('projectCanvas.statPlaceSub') },
    { num: String(mustShoot), unit: '', sub: t('projectCanvas.statMustSub') },
  ]
})
const schedScroll = ref<HTMLElement | null>(null)
const schedActive = ref(0)
function onSchedScroll() {
  const el = schedScroll.value
  if (el) schedActive.value = Math.round(el.scrollLeft / el.clientWidth)
}
function schedGo(i: number) {
  schedScroll.value?.scrollTo({ left: i * schedScroll.value.clientWidth, behavior: 'smooth' })
}
// drag-to-scroll (mouse); native swipe/trackpad works without this
let schedDrag = false, schedStartX = 0, schedStartLeft = 0, schedMoved = false
function schedDown(e: PointerEvent) {
  const el = schedScroll.value; if (!el) return
  schedDrag = true; schedMoved = false
  schedStartX = e.clientX; schedStartLeft = el.scrollLeft
}
function schedMove(e: PointerEvent) {
  if (!schedDrag || !schedScroll.value) return
  const dx = e.clientX - schedStartX
  if (Math.abs(dx) > 3) schedMoved = true
  schedScroll.value.scrollLeft = schedStartLeft - dx
}
function schedUp() {
  if (!schedDrag) return
  schedDrag = false
  // snap to nearest card after a free drag
  if (schedMoved) schedGo(schedActive.value)
}

// Each tile's metric is split into a big number (`num`) + normal-size `unit`
// (and optional small `pre` like "约"), so only the number reads large.
// When there's no data, `ph` holds the placeholder text instead.
// 内容区头部:图标 + 标题 + 一句说明,按当前标签切换(四块统一)
const DETAIL_ICONS: Record<PlanTab, any> = {
  equipment: Package, locations: MapPin, schedule: Clock, notes: TriangleAlert,
}
const DETAIL_KEY: Record<PlanTab, string> = {
  equipment: 'equip', locations: 'loc', schedule: 'sched', notes: 'notes',
}
const detailHeader = computed(() => {
  const tab = summaryTab.value
  return {
    icon:  DETAIL_ICONS[tab],
    title: t(`projectCanvas.${DETAIL_KEY[tab]}HeaderTitle`),
    desc:  t(`projectCanvas.${DETAIL_KEY[tab]}HeaderDesc`),
  }
})

const planTiles = computed(() => {
  const p = plan.value
  const eq = equipmentList.value
  const req = eq.filter(e => e.required !== false).length
  const opt = eq.filter(e => e.required === false).length
  const hasSplit = req + opt > 0
  const sched = p.schedule.length ? scheduleTotal(p.schedule) : null
  return [
    { id: 'equipment' as PlanTab, label: t('projectCanvas.tabEquipment'), icon: Package,
      num: eq.length ? String(eq.length) : '', unit: t('projectCanvas.unitItems'), ph: eq.length ? '' : t('projectCanvas.todoPlan'),
      sub: hasSplit ? t('projectCanvas.requiredOptional', { req, opt }) : '' },
    { id: 'locations' as PlanTab, label: t('projectCanvas.tabLocations'), icon: MapPin,
      num: p.locations.length ? String(p.locations.length) : '', unit: t('projectCanvas.unitPlaces'), ph: p.locations.length ? '' : t('projectCanvas.todoPlan'),
      sub: p.locations.length ? t('projectCanvas.shootScenes') : '' },
    { id: 'schedule' as PlanTab, label: t('projectCanvas.tabSchedule'), icon: Clock,
      num: p.schedule.length ? String(p.schedule.length) : '', unit: t('projectCanvas.unitSegments'), ph: p.schedule.length ? '' : t('projectCanvas.todoPlan'),
      // 头条用"段数"(计数,不折行);总时长降级到副标题
      sub: sched ? `${t('projectCanvas.totalPrefix')}${sched.pre ?? ''}${sched.num}${sched.unit}` : '' },
    { id: 'notes' as PlanTab, label: t('projectCanvas.tabNotes'), icon: TriangleAlert,
      num: notesList.value.length ? String(notesList.value.length) : '', unit: t('projectCanvas.unitPoints'), ph: notesList.value.length ? '' : t('projectCanvas.todoPlan'),
      sub: noteDoneCount.value ? t('projectCanvas.confirmedCount', { n: noteDoneCount.value }) : '' },
  ]
})

// ── Wardrobe (服装 / 道具) — left 设定 panel ─────────────────────────────────
// Character-level reference (what the coser wears / carries), stored in
// plan/wardrobe.json (separate from plan.json; the step-1 context extraction
// stays frozen). Editable list — add/remove only. No 已备/progress tracking:
// that's execution state and lives on the right-side plan (设备), not 设定.
interface CostumeItem { id?: string; name: string; category?: string; note?: string; essential?: boolean; image?: string | null }
interface PropItem { id?: string; name: string; note?: string; essential?: boolean; image?: string | null }

const COSTUME_CATEGORIES = computed(() => [
  { key: 'wig',       label: t('projectCanvas.catWig') },
  { key: 'top',       label: t('projectCanvas.catTop') },
  { key: 'bottom',    label: t('projectCanvas.catBottom') },
  { key: 'shoes',     label: t('projectCanvas.catShoes') },
  { key: 'accessory', label: t('projectCanvas.catAccessory') },
  { key: 'misc',      label: t('projectCanvas.catOther') },
])
// full URL for an item's thumbnail (backend returns a relative, cache-busted path)
const itemImg = (it: { image?: string | null }) => (it.image ? BASE_URL + it.image : '')
const costumeList = ref<CostumeItem[]>([])
const propsList   = ref<PropItem[]>([])

function loadWardrobe() {
  const w = projectData.value?.wardrobe ?? {}
  costumeList.value = (w.costume ?? []).map((c: any) => ({ ...c }))
  propsList.value   = (w.props ?? []).map((p: any) => ({ ...p }))
}

function buildWardrobe() {
  // `image` is derived on the backend (not persisted here); essential is stored.
  return {
    costume: costumeList.value.map(c => ({ id: c.id, name: c.name, category: c.category, note: c.note, essential: c.essential !== false })),
    props:   propsList.value.map(p => ({ id: p.id, name: p.name, note: p.note, essential: p.essential !== false })),
  }
}

let wardrobeSaveTimer: ReturnType<typeof setTimeout> | null = null
function persistWardrobe() {
  if (!projectData.value) return
  // costumeList/propsList are the reactive source for the template; we don't
  // overwrite projectData.wardrobe here (it would drop the derived image URLs).
  const data = buildWardrobe()
  if (wardrobeSaveTimer) clearTimeout(wardrobeSaveTimer)
  wardrobeSaveTimer = setTimeout(() => {
    api.saveWardrobe(projectId.value, data).catch(e => console.error('Failed to save wardrobe', e))
  }, 400)
}

// costume grouped by category, in canonical order, only non-empty groups
const costumeGroups = computed(() =>
  COSTUME_CATEGORIES.value
    .map(c => ({ ...c, items: costumeList.value.filter(x => (x.category || 'misc') === c.key) }))
    .filter(g => g.items.length))

// category groups collapse by default (常态收起, saves vertical space)
const openCats = reactive<Record<string, boolean>>({})
function toggleCat(key: string) { openCats[key] = !openCats[key] }

// Unified collapsible groups: each costume category (假发/上衣/…) + 道具 are all
// top-level peers (假发 parallel with 服装; 道具 collapses like the rest).
const wardrobeGroups = computed(() => {
  const groups = costumeGroups.value.map(g => ({ key: g.key, label: g.label, items: g.items }))
  if (propsList.value.length) {
    groups.push({ key: 'props', label: t('projectCanvas.subProps'), items: propsList.value })
  }
  return groups
})
function removeItem(item: any) {
  if (costumeList.value.includes(item)) removeCostume(item)
  else removeProp(item)
}
const wardrobeTotal = computed(() => costumeList.value.length + propsList.value.length)
const groupPreview = (items: any[]) => items.map(i => i.name).join('、')

// Per-category left icon + tint hue (Lucide where a fit exists; wig/bottom reuse
// the closest — see note to user re: custom SVGs for exact glyphs). Tint uses
// color-mix so it reads on both light and dark themes.
const CAT_STYLE: Record<string, { icon: any; hue: string }> = {
  wig:       { icon: Scissors,   hue: '#e26aa0' },
  top:       { icon: Shirt,      hue: '#9a8cf0' },
  bottom:    { icon: Shirt,      hue: '#6aa0f0' },
  shoes:     { icon: Footprints, hue: '#5fbf8a' },
  accessory: { icon: Gem,        hue: '#f0a860' },
  misc:      { icon: Package,    hue: '#9aa0b0' },
  props:     { icon: Package,    hue: '#e07a9a' },
}
const catStyle = (k: string) => CAT_STYLE[k] || CAT_STYLE.misc

function removeCostume(item: CostumeItem) {
  const i = costumeList.value.indexOf(item)
  if (i >= 0) costumeList.value.splice(i, 1)
  persistWardrobe()
}
function removeProp(item: PropItem) {
  const i = propsList.value.indexOf(item)
  if (i >= 0) propsList.value.splice(i, 1)
  persistWardrobe()
}

// Unified add form: one 添加 for both costume and props. The category dropdown
// includes 道具 as an option — picking it adds a prop, otherwise a costume item.
const showAdd = ref(false)
const newItem = reactive({ category: 'top', name: '', note: '' })
const ADD_CATEGORIES = computed(() => [...COSTUME_CATEGORIES.value, { key: 'props', label: t('projectCanvas.subProps') }])
function submitAdd() {
  const name = newItem.name.trim()
  if (!name) return
  const note = newItem.note.trim() || undefined
  if (newItem.category === 'props') {
    propsList.value.push({ name, note, essential: true })
  } else {
    costumeList.value.push({ category: newItem.category, name, note, essential: true })
  }
  newItem.name = ''; newItem.note = ''
  showAdd.value = false
  persistWardrobe()
}

// header summary badge counts
const costumeCount = computed(() => costumeList.value.length)
const propsCount = computed(() => propsList.value.length)

// per-item kebab menu (one open at a time); close on any outside click
const openItemMenu = ref<string | null>(null)
if (typeof window !== 'undefined') {
  window.addEventListener('click', () => { openItemMenu.value = null })
}
function toggleItemMenu(id?: string) {
  if (!id) return
  openItemMenu.value = openItemMenu.value === id ? null : id
}
function toggleEssential(item: { essential?: boolean }) {
  item.essential = item.essential === false ? true : false
  openItemMenu.value = null
  persistWardrobe()
}
async function onUploadItemImage(e: Event, item: { id?: string; image?: string | null }) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !item.id) return
  try {
    const { url } = await api.uploadWardrobeImage(projectId.value, item.id, file)
    item.image = url   // cache-busted URL from backend → thumbnail updates
  } catch (err) {
    console.error('wardrobe image upload failed', err)
  } finally {
    input.value = ''
    openItemMenu.value = null
  }
}

const exporting = ref(false)
async function doExport() {
  exporting.value = true
  try {
    await api.exportProject(projectId.value)
  } catch (e) {
    console.error('Export failed', e)
  }
  exporting.value = false
}

onMounted(async () => {
  try {
    projectData.value = await api.getProject(projectId.value)
    const savedHistory: { role: string; text: string }[] = projectData.value?.plan?.chat_history ?? []
    if (savedHistory.length > 0) {
      aiMessages.value = savedHistory
    }
    syncPlanFromData()
    loadWardrobe()
    loadMoments()
    autoGrabCoverIfMissing()      // one-time: grab a cover if the project has none
    autoGenerateMomentsIfMissing()  // one-time: silently generate 名场面 in the background
  } catch (e) {
    console.error('Failed to load project', e)
  }
})

// ── Shots ─────────────────────────────────────────────────
const shots    = computed<any[]>(() => projectData.value?.shots ?? [])
const viewMode = ref<'grid' | 'list'>('grid')
const shotAdding = ref(false)

async function quickAddShot() {
  if (shotAdding.value) return
  shotAdding.value = true
  const n = (projectData.value?.shots?.length ?? 0) + 1
  const title = t('projectCanvas.newShotName', { n })
  try {
    const shot = await api.createShot(projectId.value, title, '')
    if (projectData.value) {
      projectData.value.shots = [...(projectData.value.shots ?? []), shot]
    }
    navigateTo(`/projects/${projectId.value}/shots/${shot.shot_id}`)
  } catch (e) {
    console.error('Failed to create shot', e)
  }
  shotAdding.value = false
}

async function removeShot(shotId: string) {
  try {
    await api.deleteShot(projectId.value, shotId)
    if (projectData.value) {
      projectData.value.shots = projectData.value.shots.filter((s: any) => s.shot_id !== shotId)
    }
  } catch (e) {
    console.error('Failed to delete shot', e)
  }
}


// ── AI assistant ──────────────────────────────────────────
const GREETING = t('projectCanvas.aiGreeting')
const aiContainer = ref<HTMLElement | null>(null)
const aiInput     = ref('')
const aiLoading   = ref(false)
const aiExpanded  = ref(false)   // floating widget: collapsed (latest reply) vs full log
const aiDrag = useDraggableCorner('workspace-ai-pos')   // drag the avatar to reposition
const aiMessages  = ref<{ role: string; text: string; retryText?: string }[]>([
  { role: 'agent', text: GREETING },
])
// Collapsed bubble shows only the assistant's side — the user's own sent text
// lives in the expanded log.
const latestAgentMessage = computed(() => {
  for (let i = aiMessages.value.length - 1; i >= 0; i--) {
    if (aiMessages.value[i].role === 'agent') return aiMessages.value[i]
  }
  return null
})

function onAiInputEnter(e: KeyboardEvent) {
  if (e.isComposing) return
  e.preventDefault()
  sendAiMessage()
}

async function sendAiMessage(retryText?: string) {
  const text = retryText ?? aiInput.value.trim()
  if (!text || aiLoading.value) return
  // history = all messages before this new one
  const history = [...aiMessages.value]
  if (retryText === undefined) {
    aiInput.value = ''
    aiMessages.value.push({ role: 'user', text })
  }
  aiLoading.value = true
  await nextTick()
  if (aiContainer.value) aiContainer.value.scrollTop = aiContainer.value.scrollHeight
  try {
    const { reply, brief, plan: newPlan } = await withRetry(() => api.projectChat(projectId.value, text, history))
    aiMessages.value.push({ role: 'agent', text: reply })
    if (brief && projectData.value) {
      projectData.value.plan = { ...projectData.value.plan, brief }
    }
    // AI edited the plan panel this turn → adopt the fresh data + re-sync the UI.
    if (newPlan && projectData.value) {
      projectData.value.plan = { ...projectData.value.plan, data: newPlan }
      syncPlanFromData()
    }
  } catch {
    aiMessages.value.push({ role: 'agent', text: t('projectCanvas.aiError'), retryText: text })
  } finally {
    // Guaranteed to run even if something above throws unexpectedly —
    // the input/send button must never stay stuck disabled.
    aiLoading.value = false
  }
  await nextTick()
  if (aiContainer.value) aiContainer.value.scrollTop = aiContainer.value.scrollHeight
}

// ── Dock layout ───────────────────────────────────────────
const panelTitles = computed<Record<string, string>>(() => ({
  shots:    t('projectCanvas.panelShots'),
  summary:  t('projectCanvas.panelSummary'),
  settings: t('projectCanvas.panelSettings'),
}))

const defaultLayout = (): LayoutNode => ({
  type: 'split', dir: 'h', ratio: 22,
  a: { type: 'panel', id: 'settings' },
  b: {
    type: 'split', dir: 'h', ratio: 70,
    a: { type: 'panel', id: 'shots' },     // AI moved to a floating widget
    b: { type: 'panel', id: 'summary' },
  },
})

const layout    = ref<LayoutNode>(defaultLayout())
const dragging  = ref<PanelId | null>(null)
const hoverInfo = ref<{ panelId: PanelId; edge: Edge } | null>(null)
const collapsed = ref<PanelId[]>([])
let   ghostEl: HTMLElement | null = null

function resetLayout() { layout.value = defaultLayout(); collapsed.value = [] }

function toggleCollapse(id: PanelId) {
  const idx = collapsed.value.indexOf(id)
  if (idx === -1) collapsed.value.push(id)
  else collapsed.value.splice(idx, 1)
}

// ── Drag (mouse events) ───────────────────────────────────
function startDrag(panelId: PanelId) {
  dragging.value = panelId

  ghostEl = document.createElement('div')
  ghostEl.textContent = panelTitles.value[panelId]
  ghostEl.style.cssText = [
    'position:fixed', 'pointer-events:none', 'z-index:9999',
    'background:var(--avatar-bg)', 'border:1px solid var(--accent)', 'border-radius:6px',
    'padding:4px 14px', 'font-size:12px', 'color:var(--text-accent)',
    'opacity:0', 'transition:opacity 0.1s', 'white-space:nowrap',
    'left:-999px', 'top:-999px',
  ].join(';')
  document.body.appendChild(ghostEl)
  requestAnimationFrame(() => { if (ghostEl) ghostEl.style.opacity = '0.9' })

  window.addEventListener('mouseup', onMouseUp, { once: true })
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!dragging.value) return

  if (ghostEl) {
    ghostEl.style.left = `${e.clientX + 14}px`
    ghostEl.style.top  = `${e.clientY - 12}px`
  }

  const els = document.elementsFromPoint(e.clientX, e.clientY) as HTMLElement[]
  const panelEl = els.find(el => el.dataset?.panelId && el.dataset.panelId !== dragging.value)

  if (!panelEl) { hoverInfo.value = null; return }

  const rect   = panelEl.getBoundingClientRect()
  const xRatio = (e.clientX - rect.left)  / rect.width
  const yRatio = (e.clientY - rect.top)   / rect.height
  const T      = 0.25

  let edge: Edge | null = null
  if      (xRatio < T)     edge = 'left'
  else if (xRatio > 1 - T) edge = 'right'
  else if (yRatio < T)     edge = 'top'
  else if (yRatio > 1 - T) edge = 'bottom'

  hoverInfo.value = edge ? { panelId: panelEl.dataset.panelId as PanelId, edge } : null
}

function onMouseUp() {
  if (hoverInfo.value && dragging.value) {
    handleMove({ target: hoverInfo.value.panelId, panel: dragging.value, edge: hoverInfo.value.edge })
  }
  if (ghostEl) { ghostEl.remove(); ghostEl = null }
  dragging.value  = null
  hoverInfo.value = null
}

// ── Layout tree operations ────────────────────────────────
function removePanel(node: LayoutNode, id: PanelId): LayoutNode | null {
  if (node.type === 'panel') return node.id === id ? null : node
  const a = removePanel(node.a, id)
  const b = removePanel(node.b, id)
  if (a === null) return b
  if (b === null) return a
  return { ...node, a, b }
}

function insertPanel(node: LayoutNode, targetId: PanelId, panel: LayoutNode, edge: Edge): LayoutNode {
  if (node.type === 'panel') {
    if (node.id !== targetId) return node
    const dir: 'h' | 'v' = edge === 'left' || edge === 'right' ? 'h' : 'v'
    const before = edge === 'left' || edge === 'top'
    return { type: 'split', dir, ratio: 50, a: before ? panel : node, b: before ? node : panel }
  }
  return { ...node, a: insertPanel(node.a, targetId, panel, edge), b: insertPanel(node.b, targetId, panel, edge) }
}

function handleMove({ target, panel, edge }: { target: PanelId; panel: PanelId; edge: Edge }) {
  if (target === panel) return
  const panelNode: LayoutNode = { type: 'panel', id: panel }
  const without = removePanel(layout.value, panel)
  if (!without) return
  layout.value = insertPanel(without, target, panelNode, edge)
  dragging.value = null
}
</script>

<style scoped>
.project-page {
  height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Top bar ── */
.top-bar {
  height: 48px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}
.breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.back-btn {
  display: flex; align-items: center; gap: 1px;
  background: none; border: none; padding: 0; border-radius: 6px;
  color: var(--accent); font-size: 13px; font-weight: 500; cursor: pointer;
  transition: opacity 0.15s;
}
.back-btn:hover { opacity: 0.65; }
.back-chevron { font-size: 18px; line-height: 1; margin-top: -1px; }
.bc-sep     { color: var(--border-md); }
.bc-item    { color: var(--text-dim); }
.bc-current { color: var(--text-accent); font-weight: 600; }
.tb-actions { display: flex; gap: 8px; }
.tb-btn {
  padding: 5px 14px; background: var(--border); border: 1px solid var(--border-strong);
  border-radius: 6px; color: var(--text-muted); font-size: 12px; cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tb-btn:hover { background: var(--border-md); color: var(--text); }

/* ── Canvas ── */
.canvas { flex: 1; overflow: hidden; padding: 10px; box-sizing: border-box; }

/* ── Shared pane inner ── */
.p-inner {
  padding: 18px 20px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}
.p-inner.shots-panel { padding: 14px 16px; }

/* ── 拍摄计划 ── */
.shots-panel { display: flex; flex-direction: column; gap: 12px; padding: 14px 16px; }
.shots-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.shots-count { font-size: 11px; color: var(--text-ghost); }
.view-toggle { display: flex; gap: 2px; }
.vt-btn {
  width: 28px; height: 28px; border: none; background: none;
  color: var(--text-ghost); cursor: pointer; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.12s, color 0.12s;
}
.vt-btn:hover { background: var(--surface-inset); color: var(--text-muted); }
.vt-btn.active { background: var(--surface-inset); color: var(--accent); }

.shots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.shot-card {
  min-height: 130px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px;
  padding: 0; display: flex; flex-direction: column; gap: 0;
  cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
  overflow: hidden;
}
.shot-card:hover { border-color: var(--accent-dim); box-shadow: 0 2px 12px var(--shadow); }
.shot-card-refined { border-color: var(--badge-done-text); }
.shot-card-no-thumb { padding: 12px; }
.shot-card-no-thumb .sc-mood  { padding: 0; }
.shot-card-no-thumb .sc-title { padding: 0; }
.shot-card-no-thumb .sc-desc  { padding: 0; }
.shot-card-no-thumb .sc-footer { padding: 6px 0 0; }
.sc-thumb-wrap {
  width: 100%; overflow: hidden; flex-shrink: 0;
  background: var(--surface-inset); position: relative;
}
.sc-thumb {
  width: 100%; height: 120px; object-fit: cover; display: block;
}
.sc-mood  { font-size: 10px; color: var(--accent); padding: 10px 12px 0; }
.sc-title { font-size: 13px; font-weight: 600; color: var(--text-hi); line-height: 1.3; padding: 4px 12px 0; }
.sc-desc  { font-size: 11px; color: var(--text-dim); line-height: 1.4; margin-top: 2px; flex: 1; padding: 0 12px; }
.sc-footer {
  display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding: 6px 12px 10px;
}
.sc-spacer { flex: 1; }
.sc-error-dot {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--error); color: white;
  font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.sc-refined-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: rgba(0,0,0,0.45);
  color: white; font-size: 10px; font-weight: 600;
  text-align: center; padding: 4px 0;
  letter-spacing: 0.04em;
}
.sc-del {
  background: none; border: none; color: var(--text-ghost); font-size: 10px;
  cursor: pointer; padding: 2px 4px; border-radius: 3px; line-height: 1;
  transition: color 0.15s, background 0.15s;
}
.sc-del:hover { color: var(--error); background: var(--surface-inset); }

/* ── List view ── */
.shots-list { display: flex; flex-direction: column; gap: 6px; }
.sl-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface);
  cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
}
.sl-row:hover { border-color: var(--accent-dim); box-shadow: 0 1px 8px var(--shadow); }
.sl-refined { border-color: var(--badge-done-text); }
.sl-thumb-wrap {
  width: 44px; height: 44px; flex-shrink: 0;
  border-radius: 6px; overflow: hidden; background: var(--surface-inset);
  display: flex; align-items: center; justify-content: center;
}
.sl-thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.sl-thumb-empty { font-size: 10px; color: var(--text-ghost); }
.sl-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.sl-title { font-size: 12px; font-weight: 600; color: var(--text-hi); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sl-mood  { font-size: 10px; color: var(--accent); }
.sl-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.sl-badge-refined {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--badge-done-bg); color: var(--badge-done-text); font-weight: 600;
}
.sl-badge-error {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--surface-inset); color: var(--error);
}
.sl-add {
  margin-top: 4px; padding: 8px; width: 100%;
  border: 1.5px dashed var(--border); border-radius: 10px;
  background: none; color: var(--text-ghost); font-size: 12px;
  cursor: pointer; transition: border-color 0.15s, color 0.15s;
}
.sl-add:hover { border-color: var(--accent-dim); color: var(--accent); }

.shot-add {
  min-height: 130px; background: var(--surface-inset);
  border: 1.5px dashed var(--border); border-radius: 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  cursor: pointer; transition: border-color 0.2s;
}
.shot-add:hover { border-color: var(--accent-dim); }
.shot-add.adding { opacity: 0.6; cursor: not-allowed; }
.add-icon { font-size: 20px; color: var(--text-ghost); }
.add-text { font-size: 11px; color: var(--text-ghost); }

/* ── Summary ── */
/* ── Plan panel (right): overview card + metric tiles + detail ── */
/* Tighter edge padding than the default .p-inner (18px 20px) so the cards sit
   closer to the panel border. Column-flex so the detail card fills the rest. */
.plan-panel { display: flex; flex-direction: column; gap: 12px; padding: 12px; height: 100%; box-sizing: border-box; }

/* 项目概览:卡片式 */
.plan-card {
  border: 1px solid var(--border); border-radius: 12px;
  padding: 10px 12px; background: var(--surface);
  display: flex; flex-direction: column; gap: 9px;
}
.pc-head  { display: flex; align-items: center; }
/* Section titles match the dock panel title ("拍摄总结" → var(--text-2)) */
.pc-title { font-size: 12px; font-weight: 600; color: var(--text-2); }
.pc-rows  { display: flex; flex-direction: column; gap: 8px; }
.po-row   { display: flex; gap: 10px; align-items: baseline; }
.po-label { font-size: 11px; color: var(--text-quiet); flex-shrink: 0; width: 52px; }
.po-val   { font-size: 12px; color: var(--text-hi); line-height: 1.5; min-width: 0; }
.po-val.ph { color: var(--text-ghost); }
.po-input {
  flex: 1; min-width: 0; font-size: 12px; font-family: inherit;
  color: var(--text-hi); background: transparent;
  border: none; border-bottom: 1px solid transparent;
  padding: 1px 0; outline: none; transition: border-color 0.15s;
}
.po-input::placeholder { color: var(--text-ghost); }
.po-input:hover  { border-bottom-color: var(--border); }
.po-input:focus  { border-bottom-color: var(--accent-dim); }

/* 连体式标签页:选中方块与下方内容区共用背景、无底边框而无缝相连;
   未选中方块用不同背景 + 完整边框,与内容区分离。
   标签行比内容区窄(左右缩进),内容区撑满面板剩余高度。 */
.plan-tabs { position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.plan-tiles {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px;
  position: relative; z-index: 2; margin: 0 8px -1px;
}
.plan-tile {
  display: flex; flex-direction: column; gap: 3px; text-align: left;
  padding: 8px 7px; cursor: pointer; min-width: 0;
  border: 1px solid var(--border); border-radius: 9px 9px 0 0;
  background: var(--surface-inset);
  transition: background 0.15s, border-color 0.15s;
}
.plan-tile:hover:not(.active) { background: var(--surface-raised); }
/* active: same bg as the content panel + no bottom border → merges seamlessly */
.plan-tile.active {
  background: var(--surface);
  border-color: var(--border);
  border-bottom-color: var(--surface);
}
.pt-label  { display: flex; align-items: center; gap: 3px; font-size: 10px; font-weight: 600; color: var(--text-2); white-space: nowrap; }
.pt-ico    { width: 12px; height: 12px; flex-shrink: 0; color: var(--text-quiet); stroke-width: 2; }
/* metric = big number + normal-size unit (参考图那种:数字大、文字常规)。
   nowrap:所有指标都是"计数"(N项/个/段/点),永不折行,抗多语言宽度变化。 */
.pt-metric { display: flex; align-items: baseline; gap: 1px; line-height: 1.15; white-space: nowrap; }
.pt-num  { font-size: 19px; font-weight: 700; color: var(--text-hi); }
.pt-unit { font-size: 11px; font-weight: 500; color: var(--text-muted); }
.pt-metric.ph { font-size: 11px; font-weight: 500; color: var(--text-ghost); white-space: nowrap; }
/* 副标题单行:换语言变长时省略号截断(hover 看全文),而不是折行撑高方块 */
.pt-sub    {
  font-size: 9px; color: var(--text-quiet); min-height: 11px; line-height: 1.3;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
}

.plan-detail {
  position: relative; z-index: 1; flex: 1; min-height: 44px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px; overflow-y: auto;
}
/* 场地:按地点的卡片(地点名 + 这里拍哪些镜头/多久),无封面 */
.loc-list { display: flex; flex-direction: column; gap: 8px; }
.loc-card {
  padding: 10px 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
.loc-body { min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.loc-line1 { display: flex; align-items: center; gap: 8px; }
.loc-name { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: var(--text-hi); line-height: 1.3; }
/* 室内/室外/棚子:自动判定,只读小标签 */
.loc-type {
  flex-shrink: 0; font-size: 10px; font-weight: 600;
  border: 1px solid var(--accent-dim); border-radius: 5px; padding: 1px 7px;
  color: var(--accent);
}
.loc-meta { display: flex; flex-wrap: wrap; gap: 3px 12px; }
.loc-mrow { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-quiet); }
.loc-mi { width: 12px; height: 12px; flex-shrink: 0; }
/* 光线 / 地址:可填,轻样式(平时无边框,hover/focus 出下划线) */
.loc-field { display: flex; align-items: center; gap: 5px; }
.loc-fi { width: 12px; height: 12px; flex-shrink: 0; color: var(--text-quiet); }
.loc-input {
  flex: 1; min-width: 0; font-size: 11px; font-family: inherit;
  color: var(--text-hi); background: transparent;
  border: none; border-bottom: 1px solid transparent; padding: 1px 0; outline: none;
  transition: border-color 0.15s;
}
.loc-input::placeholder { color: var(--text-ghost); }
.loc-input:hover  { border-bottom-color: var(--border); }
.loc-input:focus  { border-bottom-color: var(--accent-dim); }
.detail-empty { font-size: 12px; color: var(--text-ghost); margin: 4px 0; }
/* 注意事项条目:窄栏适配 —— checkbox + 正文(标题/删除、细节、状态+优先级) */
.note-item {
  display: flex; align-items: flex-start; gap: 9px;
  padding: 9px 10px; border-radius: 9px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
.note-item.is-ready { border-color: var(--accent-dim); }
.note-item .ei-check { margin-top: 1px; }
.ni-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.ni-line1 { display: flex; align-items: flex-start; gap: 6px; }
.ni-title { flex: 1; min-width: 0; font-size: 12.5px; font-weight: 600; color: var(--text-hi); line-height: 1.4; }
.ni-desc  { font-size: 10.5px; color: var(--text-quiet); line-height: 1.5; }
.ni-meta  { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 1px; flex-wrap: wrap; }
/* 优先级药丸(主题色,不写死红):高=error 中=orange 低=quiet */
.ni-prio {
  font-size: 10px; font-weight: 600; border-radius: 5px; padding: 1px 7px;
  border: 1px solid transparent;
}
.ni-prio.p-high { color: var(--error);  border-color: var(--error);  }
.ni-prio.p-mid  { color: var(--orange); border-color: var(--orange); }
.ni-prio.p-low  { color: var(--text-quiet); border-color: var(--border); }

/* 角色头像选择器 */
.char-picker { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.char-ava {
  display: flex; flex-direction: column; align-items: center; gap: 5px;
  width: 60px; padding: 0; background: none; border: none; cursor: pointer;
}
.ca-img {
  width: 52px; height: 52px; border-radius: 50%; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface-inset); border: 2px solid var(--border-md);
  transition: border-color 0.15s, transform 0.15s;
}
.ca-img img { width: 100%; height: 100%; object-fit: cover; }
.ca-ph { font-size: 20px; font-weight: 700; color: var(--text-quiet); }
.char-ava:hover .ca-img { border-color: var(--accent-dim); }
.char-ava.on .ca-img { border-color: var(--accent); transform: scale(1.04); }
.char-ava.on .ca-name { color: var(--accent); font-weight: 700; }
.ca-img { position: relative; }
.ca-edit {
  position: absolute; right: -1px; bottom: -1px;
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid var(--surface); opacity: 0; transition: opacity 0.15s;
}
.char-ava.on:hover .ca-edit { opacity: 1; }
.ca-edit :deep(svg) { width: 10px; height: 10px; }
.ca-name {
  font-size: 10.5px; color: var(--text-quiet); max-width: 60px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ca-img.add { border-style: dashed; color: var(--text-quiet); }
.ca-img.add :deep(svg) { width: 20px; height: 20px; }
.char-ava.add:hover .ca-img.add { color: var(--accent); border-color: var(--accent-dim); }

/* 三段标签导航 */
.char-tabs {
  display: flex; gap: 4px; margin-bottom: 14px;
  background: var(--surface-inset); border: 1px solid var(--border); border-radius: 10px; padding: 3px;
}
.char-tab {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 5px;
  padding: 7px 6px; border-radius: 7px; cursor: pointer;
  font-size: 11.5px; font-weight: 600; color: var(--text-quiet);
  background: none; border: none; transition: background 0.15s, color 0.15s;
}
.char-tab:hover { color: var(--text-2); }
.char-tab.on { background: var(--surface); color: var(--accent); box-shadow: 0 1px 4px var(--shadow); }
.ct-ico { width: 13px; height: 13px; flex-shrink: 0; }

/* 每段内容的小节标题 */
.char-panel { display: flex; flex-direction: column; }
.cp-sub {
  font-size: 11px; font-weight: 700; color: var(--text-2);
  margin: 14px 0 8px; letter-spacing: 0.02em;
}
.cp-sub:first-child { margin-top: 2px; }

/* 名场面 (signature scenes) — detailed cards */
.mo { display: flex; flex-direction: column; gap: 10px; }
.mo-list { display: flex; flex-direction: column; gap: 9px; }
.mo-card {
  display: flex; flex-direction: column; gap: 5px;
  padding: 11px 12px; border-radius: 11px;
  background: var(--surface-inset); border: 1px solid var(--border);
}
.mo-head { display: flex; align-items: center; gap: 8px; }
.mo-num {
  flex-shrink: 0; width: 18px; height: 18px; border-radius: 50%;
  background: var(--accent); color: #fff; font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.mo-title { flex: 1; min-width: 0; font-size: 12.5px; font-weight: 700; color: var(--text-hi); line-height: 1.4; }
.mo-source {
  align-self: flex-start; font-size: 10px; font-weight: 600; color: var(--text-2);
  padding: 2px 8px; border-radius: 6px; background: var(--surface-raised); margin-left: 26px;
}
.mo-desc { font-size: 11.5px; color: var(--text-quiet); line-height: 1.6; margin-left: 26px; }

.mo-ta { resize: vertical; font-family: inherit; line-height: 1.5; }

/* 配色 swatches (hover shows name + hex via native title) */
.swatches { display: flex; flex-wrap: wrap; gap: 7px; padding-top: 1px; }
.swatch {
  width: 22px; height: 22px; border-radius: 6px; cursor: default;
  border: 1px solid var(--border-md);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.15);
}

/* 人物关系 */
.rel-list { display: flex; flex-direction: column; gap: 7px; }
.rel-item {
  display: flex; align-items: baseline; gap: 8px;
  padding: 8px 10px; border-radius: 9px;
  background: var(--surface-inset); border: 1px solid var(--border);
}
.rel-name { flex-shrink: 0; font-size: 12px; font-weight: 700; color: var(--text-hi); }
.rel-rel { font-size: 11px; color: var(--text-quiet); line-height: 1.5; }

/* transient toast (bottom-center) */
.toast {
  position: fixed; left: 50%; bottom: 32px; transform: translateX(-50%);
  z-index: 10000; padding: 9px 18px; border-radius: 10px;
  font-size: 12.5px; font-weight: 600; color: var(--text-hi);
  background: var(--surface-raised); border: 1px solid var(--border-md);
  box-shadow: 0 6px 24px var(--shadow); white-space: nowrap;
}
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* Wardrobe (服装/道具) section sub-headers in the left 设定 panel */
.wd-sub {
  display: flex; align-items: center; gap: 6px; margin-top: 2px;
  font-size: 11.5px; font-weight: 700; color: var(--text-2);
}
.wd-si { width: 14px; height: 14px; color: var(--accent); flex-shrink: 0; }

/* ── Wardrobe card list ─────────────────────────────────── */
.wd { display: flex; flex-direction: column; gap: 10px; }
.wd-head { display: flex; align-items: center; justify-content: flex-start; margin-top: 2px; }
.wd-add-row { display: flex; gap: 8px; }
.wd-add-row .equip-add-btn { flex: 1; }
.wd-badge {
  font-size: 11px; font-weight: 600; color: var(--text-2);
  padding: 3px 10px; border-radius: 999px;
  background: var(--surface-inset); border: 1px solid var(--border-md);
}
.wd-group { display: flex; flex-direction: column; gap: 8px; }
/* category card (collapsed row): left tinted icon + name/count + preview + chevron */
.wd-cat {
  display: flex; align-items: center; gap: 11px; width: 100%;
  padding: 10px 12px; border-radius: 12px; cursor: pointer;
  background: var(--surface); border: 1px solid var(--border);
  text-align: left; transition: border-color 0.15s, box-shadow 0.15s;
}
.wd-cat:hover { border-color: var(--accent-dim); box-shadow: 0 2px 10px var(--shadow); }
.wd-cat-ico {
  width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}
.wd-cat-ico :deep(svg) { width: 20px; height: 20px; }
.wd-cat-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.wd-cat-line1 { display: flex; align-items: center; gap: 7px; }
.wd-cat-name { font-size: 13px; font-weight: 700; color: var(--text-2); }
.wd-cat-count {
  font-size: 10.5px; font-weight: 700; color: var(--accent);
  min-width: 17px; height: 17px; padding: 0 5px; border-radius: 9px;
  background: var(--surface-inset); display: inline-flex; align-items: center; justify-content: center;
}
.wd-cat-preview {
  font-size: 11px; color: var(--text-quiet); line-height: 1.4;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.wd-gh-chev {
  width: 16px; height: 16px; flex-shrink: 0; color: var(--text-quiet);
  transition: transform 0.2s; transform: rotate(-90deg);
}
.wd-gh-chev.open { transform: rotate(0deg); }

/* add cards (服装 / 道具): same card language, left + icon */
.wd-add-card {
  flex: 1; display: flex; align-items: center; gap: 9px;
  padding: 10px 12px; border-radius: 12px; cursor: pointer;
  background: none; border: 1px dashed var(--border-focus);
  color: var(--accent); font-size: 12.5px; font-weight: 600;
  transition: background 0.15s, border-color 0.15s;
}
.wd-add-card.single { width: 100%; justify-content: center; }
.wd-add-card:hover { background: var(--surface-inset); border-color: var(--accent-dim); }
.wd-add-ico {
  width: 30px; height: 30px; flex-shrink: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent);
}
.wd-add-ico :deep(svg) { width: 16px; height: 16px; }

.wd-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px; border-radius: 11px;
  background: var(--surface-inset); border: 1px solid var(--border);
}
.wd-thumb {
  width: 48px; height: 48px; flex-shrink: 0; border-radius: 9px; overflow: hidden;
  background: var(--surface-raised); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
}
.wd-thumb img { width: 100%; height: 100%; object-fit: cover; }
.wd-thumb-ph { width: 20px; height: 20px; color: var(--text-ghost); }
.wd-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.wd-name { font-size: 12.5px; font-weight: 600; color: var(--text-hi); line-height: 1.35; }
.wd-note { font-size: 10.5px; color: var(--text-quiet); line-height: 1.4; }
.wd-pill {
  flex-shrink: 0; font-size: 10px; font-weight: 700;
  padding: 3px 9px; border-radius: 999px; white-space: nowrap;
}
.wd-pill.ess { color: var(--accent); background: var(--accent-soft, var(--surface-raised)); border: 1px solid var(--accent-dim); }
.wd-pill.backup { color: #fff; background: var(--accent-dim); border: 1px solid var(--accent-dim); }

.wd-menu-wrap { position: relative; flex-shrink: 0; }
.wd-kebab {
  width: 24px; height: 24px; padding: 0; border: none; background: none; cursor: pointer;
  color: var(--text-quiet); border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
}
.wd-kebab:hover { background: var(--surface-raised); color: var(--text-2); }
.wd-kebab :deep(svg) { width: 15px; height: 15px; }
.wd-menu {
  position: absolute; right: 0; top: 28px; z-index: 20; min-width: 130px;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 10px;
  box-shadow: 0 8px 24px var(--shadow); padding: 4px; display: flex; flex-direction: column; gap: 1px;
}
.wd-mi {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 8px 10px; border: none; background: none; cursor: pointer;
  font-size: 12px; color: var(--text-hi); border-radius: 7px; text-align: left;
}
.wd-mi:hover { background: var(--surface-inset); }
.wd-mi.danger { color: var(--error); }
.wd-mi :deep(svg) { width: 14px; height: 14px; flex-shrink: 0; }

/* Equipment detail — summary line + 准备进度 + 必要/可选 grouped cards */
.equip { display: flex; flex-direction: column; gap: 14px; }
/* 内容区头部:图标 + 标题 + 说明 */
.detail-header { display: flex; align-items: flex-start; gap: 9px; margin-bottom: 14px; }
.dh-icon {
  flex-shrink: 0; width: 30px; height: 30px; border-radius: 8px;
  background: var(--surface-inset);
  display: flex; align-items: center; justify-content: center; color: var(--accent);
}
.dh-icon :deep(svg) { width: 17px; height: 17px; stroke-width: 2; }
.dh-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.dh-title { font-size: 13px; font-weight: 700; color: var(--text-hi); line-height: 1.3; }
.dh-desc  { font-size: 11px; color: var(--text-quiet); line-height: 1.55; }

/* 准备进度条 */
.prep-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 9px; background: var(--surface-inset);
}
.pb-head { display: flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600; color: var(--text-2); white-space: nowrap; }
.pb-ico  { width: 13px; height: 13px; color: var(--accent); }
.pb-track { flex: 1; min-width: 0; height: 5px; border-radius: 3px; background: var(--border); overflow: hidden; }
.pb-fill  { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.25s ease; }
.pb-pct   { font-size: 11px; font-weight: 700; color: var(--accent); white-space: nowrap; }

/* 每项前的勾选框 */
.ei-check {
  width: 20px; height: 20px; flex-shrink: 0; border-radius: 6px; cursor: pointer;
  border: 1.5px solid var(--border-focus); background: var(--surface);
  display: flex; align-items: center; justify-content: center; padding: 0;
  transition: background 0.15s, border-color 0.15s;
}
.ei-check.on { background: var(--accent); border-color: var(--accent); }
.ei-check-ico { width: 13px; height: 13px; color: #fff; stroke-width: 3; }

/* 右侧状态徽章 */
.ei-status {
  flex-shrink: 0; display: inline-flex; align-items: center; gap: 3px;
  font-size: 10px; font-weight: 600; white-space: nowrap;
}
.eis-ico { width: 12px; height: 12px; }
.ei-status.ready   { color: var(--accent); }
.ei-status.pending { color: var(--orange, #c9962f); }
.equip-item.is-ready { border-color: var(--accent-dim); }
.equip-group { display: flex; flex-direction: column; gap: 6px; }
.equip-group-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: var(--text-2); margin-bottom: 1px;
}
.egh-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.egh-dot.req { background: var(--accent); }
.egh-dot.opt { background: var(--border-focus); }
.egh-count { font-weight: 500; color: var(--text-quiet); }
.equip-item {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 10px; border-radius: 9px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
.ei-icon {
  width: 30px; height: 30px; flex-shrink: 0; border-radius: 7px;
  background: var(--surface-raised);
  display: flex; align-items: center; justify-content: center;
  color: var(--accent);
}
.ei-icon :deep(svg) { width: 16px; height: 16px; stroke-width: 2; }
.ei-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ei-name { font-size: 12.5px; font-weight: 600; color: var(--text-hi); line-height: 1.3; }
.ei-desc { font-size: 10.5px; color: var(--text-quiet); line-height: 1.3; }
/* × 删除按钮:平时淡,hover 变红 */
.ei-del {
  flex-shrink: 0; width: 20px; height: 20px; padding: 0; border: none;
  background: none; cursor: pointer; border-radius: 5px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-ghost); transition: color 0.15s, background 0.15s;
}
.ei-del :deep(svg) { width: 13px; height: 13px; }
.ei-del:hover { color: var(--text-2); background: var(--surface-raised); }
/* armed:二次确认态 —— 用当前主题最深的强调色(--accent-dim)做"删除"药丸,
   跟随主题;二次确认 + 文字本身已表达破坏性,不需红色。 */
.ei-del.armed {
  width: auto; padding: 0 8px; font-size: 10px; font-weight: 600;
  color: #fff; background: var(--accent-dim); white-space: nowrap;
}
.ei-del.armed:hover { color: #fff; filter: brightness(0.92); }

/* + 添加设备 按钮 + 表单 */
.equip-add-btn {
  width: 100%; padding: 8px; border-radius: 9px; cursor: pointer;
  border: 1px dashed var(--border-focus); background: none;
  color: var(--accent); font-size: 12px; font-weight: 600;
  transition: background 0.15s, border-color 0.15s;
}
.equip-add-btn:hover { background: var(--surface-inset); border-color: var(--accent-dim); }
.equip-form {
  display: flex; flex-direction: column; gap: 8px;
  padding: 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
.ef-select, .ef-input {
  width: 100%; box-sizing: border-box; font-family: inherit; font-size: 12px;
  padding: 7px 9px; border-radius: 7px; color: var(--text-hi);
  border: 1px solid var(--border-md); background: var(--surface); outline: none;
  transition: border-color 0.15s;
}
.ef-select:focus, .ef-input:focus { border-color: var(--accent-dim); }
.ef-input::placeholder { color: var(--text-ghost); }
.ef-req { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); cursor: pointer; }
.ef-req input { width: 14px; height: 14px; accent-color: var(--accent); cursor: pointer; }
.ef-row2 { display: flex; gap: 8px; }
.ef-row2 .ef-select { flex: 1; min-width: 0; }
.ef-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 2px; }
.ef-cancel, .ef-submit {
  padding: 6px 14px; border-radius: 7px; font-size: 12px; font-weight: 600; cursor: pointer;
}
.ef-cancel { border: 1px solid var(--border-md); background: none; color: var(--text-muted); }
.ef-cancel:hover { background: var(--surface-raised); }
.ef-submit { border: none; background: var(--accent); color: #fff; }
.ef-submit:hover:not(:disabled) { background: var(--accent-hover, var(--accent)); }
.ef-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* 拍摄日程:横向滑动卡片(每张=一个时段/场景),snap + 拖动 + 圆点指示 */
.sched { display: flex; flex-direction: column; gap: 12px; }
/* 头部统计:一排小方块(数字大、说明小,同方块标签风格) */
.sched-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.ss-tile {
  display: flex; flex-direction: column; gap: 2px; min-width: 0;
  padding: 8px 7px; border-radius: 9px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
.ss-metric { display: flex; align-items: baseline; gap: 1px; white-space: nowrap; line-height: 1.15; }
.ss-num  { font-size: 14px; font-weight: 700; color: var(--text-hi); }
.ss-unit, .ss-pre { font-size: 10px; font-weight: 500; color: var(--text-muted); }
.ss-sub  { font-size: 9px; color: var(--text-quiet); }
.sched-track {
  display: flex; gap: 12px; overflow-x: auto;
  scroll-snap-type: x mandatory; scrollbar-width: none;
  cursor: grab; touch-action: pan-y;   /* 允许纵向滚页面,横向自己处理 */
}
.sched-track:active { cursor: grabbing; }
.sched-track::-webkit-scrollbar { display: none; }
.sched-card {
  flex: 0 0 100%; scroll-snap-align: center; min-width: 0;
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px; border-radius: 12px;
  border: 1px solid var(--border); background: var(--surface-inset);
}
/* 卡片头:序号 + 时间/时长 + 优先级 */
.scd-hd { display: flex; align-items: center; gap: 8px; }
.scd-num {
  flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%;
  background: var(--accent); color: #fff; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.scd-time { flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 8px; }
.scd-range { font-size: 13px; font-weight: 700; color: var(--text-hi); }
.scd-dur { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; color: var(--text-quiet); }
.scd-i { width: 11px; height: 11px; }
/* 封面:该场景的 shot 图堆叠(书堆风);无图时占位 */
.scd-thumb {
  position: relative; width: 100%; aspect-ratio: 16 / 9; border-radius: 9px;
  background: var(--surface-raised); display: flex; align-items: center; justify-content: center;
}
/* 每张图片一层;后面的图往右下角错开一点,边缘露出来形成一摞 */
.scd-layer {
  position: absolute; top: 0; left: 0;
  width: calc(100% - 12px); height: calc(100% - 12px);
  border-radius: 8px; overflow: hidden; border: 1px solid var(--surface);
  box-shadow: 0 1px 4px var(--shadow, rgba(0,0,0,0.12));
}
.scd-layer img { width: 100%; height: 100%; object-fit: cover; display: block; }
.scd-count {
  position: absolute; right: 6px; bottom: 6px; z-index: 10;
  font-size: 10px; font-weight: 600; color: #fff;
  background: rgba(0,0,0,0.55); border-radius: 5px; padding: 1px 7px;
}
.scd-ph { color: var(--text-ghost); }
.scd-ph :deep(svg) { width: 26px; height: 26px; }
/* 信息行 */
.scd-info { display: flex; flex-direction: column; gap: 7px; }
.scd-row { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-muted); }
.scd-ri { width: 14px; height: 14px; flex-shrink: 0; color: var(--accent); stroke-width: 2; }
.scd-scene { font-size: 13px; font-weight: 600; color: var(--text-hi); }
.scd-k { color: var(--text-quiet); flex-shrink: 0; }
.scd-v { min-width: 0; }
/* 圆点指示 */
.sched-dots { display: flex; justify-content: center; align-items: center; gap: 6px; }
.sd-count { font-size: 11px; font-weight: 600; color: var(--text-quiet); margin-right: 4px; }
.sd-dot {
  width: 6px; height: 6px; border-radius: 50%; padding: 0; border: none; cursor: pointer;
  background: var(--border-focus); transition: background 0.15s, width 0.15s;
}
.sd-dot.on { width: 16px; border-radius: 3px; background: var(--accent); }
/* 左右滑动提示条 */
.sched-hint {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px; border-radius: 8px;
  background: var(--surface-inset); font-size: 11px; color: var(--text-quiet);
}
.sh-ico { width: 13px; height: 13px; flex-shrink: 0; color: var(--accent); }

.tags        { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  padding: 2px 7px; background: var(--surface-2); border: 1px solid var(--border-md);
  border-radius: 4px; font-size: 11px; color: var(--text-muted);
}

/* ── 设定面板 ── */
.setting-block  { margin-bottom: 22px; }
.s-section      { font-size: 13px; font-weight: 700; color: var(--text-2); margin-bottom: 12px; letter-spacing: 0; }

/* collapse chevron (背景设定 title row toggle) */
.s-chev {
  width: 16px; height: 16px; color: var(--text-quiet); flex-shrink: 0;
  margin-left: auto; transition: transform 0.2s; transform: rotate(-90deg);
}
.s-chev.open { transform: rotate(0deg); }
.s-row         { display: flex; gap: 10px; margin-bottom: 5px; align-items: baseline; }
.s-row-top     { align-items: flex-start; }
.s-key         { font-size: 10px; color: var(--text-quiet); flex-shrink: 0; width: 44px; padding-top: 1px; }
.s-val         { font-size: 12px; color: var(--text-muted); line-height: 1.5; }

/* ── 作品设定 (redesigned hero + sections) ─────────────────── */
.ws-hero { margin-bottom: 16px; }
.ws-cover {
  position: relative; width: 100%; aspect-ratio: 16/10; border-radius: 12px;
  overflow: hidden; background: var(--surface-inset); border: 1px solid var(--border);
}
.ws-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ws-cover-ph { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: var(--text-ghost); }
.ws-cover-ph :deep(svg) { width: 26px; height: 26px; }
.ws-cover-btn {
  position: absolute; right: 8px; bottom: 8px;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 9px; border-radius: 7px; cursor: pointer;
  font-size: 11px; font-weight: 600; color: #fff;
  background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.25);
  backdrop-filter: blur(4px); transition: background 0.15s;
}
.ws-cover-btn:hover:not(.disabled) { background: rgba(0,0,0,0.68); }
.ws-cover-btn.disabled { cursor: default; opacity: 0.8; }
.ws-cover-btn :deep(svg) { width: 12px; height: 12px; }
.ws-cover :deep(svg.spin) { animation: spin 0.8s linear infinite; }
.ws-title-row {
  display: flex; align-items: center; gap: 8px; width: 100%; margin-top: 10px;
  background: none; border: none; padding: 0; cursor: pointer; text-align: left;
}
.ws-hero-title { flex: 1; min-width: 0; font-size: 15px; font-weight: 800; color: var(--text-hi); line-height: 1.35; }
.ws-hero-sub {
  font-size: 11.5px; color: var(--text-muted); line-height: 1.65; margin-top: 6px;
}

/* section sub-headers (基础信息 / 氛围设定 / …) */
.ws-sub {
  display: flex; align-items: center; gap: 6px; margin: 16px 0 8px;
  font-size: 11.5px; font-weight: 700; color: var(--text-2);
}
.ws-si { width: 14px; height: 14px; color: var(--accent); flex-shrink: 0; }

/* icon-labelled key/value rows, boxed like the mockup */
.ws-info {
  display: flex; flex-direction: column;
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--surface-inset); padding: 4px 2px;
}
.ws-irow { display: flex; align-items: flex-start; gap: 7px; padding: 8px 10px; }
.ws-ii { width: 13px; height: 13px; color: var(--accent); flex-shrink: 0; margin-top: 2px; }
.ws-ik { font-size: 11px; color: var(--text-quiet); flex-shrink: 0; width: 58px; padding-top: 1px; }
.ws-iv { font-size: 12px; color: var(--text-hi); line-height: 1.5; min-width: 0; }


.ref-add-card {
  width: 100%; aspect-ratio: 2/3;
  border: 1.5px dashed var(--border);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s;
}
.ref-add-card:hover { border-color: var(--accent); }
.ref-add-card:hover .ref-add-plus { color: var(--accent); }
.ref-add-plus { font-size: 18px; color: var(--text-ghost); line-height: 1; }

.refs-mini-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 6px;
}
.ref-mini-img {
  width: 100%; aspect-ratio: 2/3; object-fit: cover;
  border-radius: 6px; border: 1px solid var(--border); display: block;
  cursor: pointer; transition: border-color 0.15s, opacity 0.15s;
}
.ref-mini-img:hover { border-color: var(--accent); opacity: 0.9; }
.ref-extra { border-style: dashed; opacity: 0.85; }

/* ── Lightbox ── */
.lightbox {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,0.88);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.lb-img-wrap { position: relative; max-height: 82vh; }
.lb-img {
  max-width: 90vw; max-height: 82vh;
  object-fit: contain; border-radius: 8px;
  display: block;
}
.lb-close {
  position: absolute; top: 16px; right: 20px;
  background: none; border: none;
  color: rgba(255,255,255,0.7); font-size: 22px;
  cursor: pointer; line-height: 1; padding: 4px;
}
.lb-close:hover { color: #fff; }
.lb-arrow {
  position: absolute; top: 50%; transform: translateY(-50%);
  background: rgba(255,255,255,0.12); border: none;
  color: #fff; font-size: 28px; line-height: 1;
  padding: 8px 14px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s;
}
.lb-arrow:hover { background: rgba(255,255,255,0.22); }
.lb-prev { left: 20px; }
.lb-next { right: 20px; }
.lb-counter {
  margin-top: 12px; font-size: 12px; color: rgba(255,255,255,0.45);
}
.lb-badge {
  position: absolute; bottom: 8px; left: 8px;
  font-size: 10px; padding: 2px 7px; border-radius: 4px;
}
.lb-badge-orig  { background: var(--accent); color: #fff; opacity: 0.85; }
.lb-badge-extra { background: var(--border-strong); color: var(--text-hi); opacity: 0.85; }

/* ── AI 助手 ── */
.ai-msg        { display: flex; gap: 8px; align-items: flex-start; }
.ai-msg.user   { flex-direction: row-reverse; }
.ai-avatar {
  width: 24px; height: 24px; border-radius: 6px; background: var(--avatar-bg);
  color: var(--avatar-text); font-size: 9px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.ai-bubble {
  max-width: 82%; padding: 7px 10px; border-radius: 8px;
  font-size: 12px; line-height: 1.5; background: var(--surface);
  color: var(--text-muted); border: 1px solid var(--border);
}
.ai-msg.user .ai-bubble {
  background: var(--bubble-user-bg);
  border-color: var(--bubble-user-bdr);
  color: var(--bubble-user-text);
}
.retry-btn {
  display: block; margin-top: 6px;
  background: none; border: 1px solid var(--border-focus); border-radius: 6px;
  padding: 3px 10px; font-size: 11px; font-weight: 600; color: var(--accent);
  cursor: pointer; transition: background 0.15s;
}
.retry-btn:hover:not(:disabled) { background: var(--surface-raised); }
.retry-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.typing { display: flex; gap: 4px; align-items: center; padding: 10px 12px; }
.typing span {
  width: 5px; height: 5px; border-radius: 50%; background: var(--text-sub);
  animation: dot 1.2s ease-in-out infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }

.ai-input {
  flex: 1; min-width: 0; background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 8px; color: var(--text-hi); font-size: 12px;
  padding: 7px 10px; font-family: inherit;
  transition: border-color 0.15s;
}
.ai-input:focus        { outline: none; border-color: var(--accent-dim); }
.ai-input::placeholder { color: var(--text-ghost); }
.ai-input:disabled     { opacity: 0.6; cursor: not-allowed; }
.ai-send {
  width: 32px; height: 32px; background: var(--accent-dim); border: none;
  border-radius: 8px; color: white; font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: background 0.15s;
}
.ai-send:hover:not(:disabled) { background: var(--accent); }
.ai-send:disabled { opacity: 0.5; cursor: not-allowed; }

/* ══ Floating AI planning assistant ══ */
.ai-widget {
  position: fixed; right: 28px; bottom: 28px; z-index: 60;
  display: flex; flex-direction: column; align-items: flex-end; gap: 10px;
}
.ai-widget-avatar {
  width: 48px; height: 48px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent); border: none; color: white;
  font-size: 12px; font-weight: 700; cursor: grab; touch-action: none;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px var(--shadow, rgba(0,0,0,0.18));
  transition: transform 0.15s;
}
.ai-widget-avatar:hover { transform: scale(1.06); }
.ai-widget-avatar:active { cursor: grabbing; }

/* collapsed: bare speech bubble showing the latest reply */
.ai-widget-bubble {
  width: 300px; max-width: calc(100vw - 56px);
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 14px; padding: 10px 14px;
  box-shadow: 0 8px 24px var(--shadow, rgba(0,0,0,0.15));
  font-size: 12.5px; line-height: 1.6; color: var(--text-hi);
}
.ai-widget-bubble.typing { display: flex; gap: 4px; align-items: center; width: auto; }

/* expanded: full history panel + input (the only place input appears) */
.ai-widget-panel {
  width: 300px; max-width: calc(100vw - 56px);
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 14px;
  box-shadow: 0 12px 32px var(--shadow, rgba(0,0,0,0.2));
  padding: 10px;
  display: flex; flex-direction: column; gap: 8px;
}
.ai-widget-log {
  max-height: 320px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px;
  padding: 2px; scrollbar-width: none;
}
.ai-widget-log::-webkit-scrollbar { display: none; }

.ai-widget-input-row {
  display: flex; gap: 6px; align-items: center;
}
</style>
