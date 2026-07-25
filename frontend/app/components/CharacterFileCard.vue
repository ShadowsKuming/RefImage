<template>
  <div class="file-card">
    <div class="fc-eyebrow">
      <span class="fc-eyebrow-mark">✿</span>
      <span>{{ series || t('newProject.pageTitle') }} · character file</span>
    </div>

    <div class="fc-grid">
      <!-- Left column -->
      <div class="fc-left">
        <h2 class="fc-name">{{ character }}</h2>
        <p v-if="series" class="fc-series">{{ series }}</p>

        <div class="fc-tab-nav">
          <button class="fc-tab-btn" :class="{ active: activeTab === 'char' }" @click="activeTab = 'char'">
            {{ t('profileViewer.charSectionTitle') }}
          </button>
          <button class="fc-tab-btn" :class="{ active: activeTab === 'world' }" @click="activeTab = 'world'">
            {{ t('profileViewer.worldSectionTitle') }}
          </button>
        </div>

        <!-- 角色 tab -->
        <template v-if="activeTab === 'char'">
          <div v-if="hasProfile" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ t('profileViewer.charSectionTitle') }} PROFILE</div>
            <div class="fc-block-body">
              <div class="fc-rows">
                <div v-if="characterBackground?.role" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('role') }}</span>
                  <span class="fc-row-val">{{ characterBackground.role }}</span>
                </div>
                <div v-if="characterBackground?.age" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('age') }}</span>
                  <span class="fc-row-val">{{ characterBackground.age }}</span>
                </div>
                <div v-if="characterBackground?.backstory" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('backstory') }}</span>
                  <span class="fc-row-val">{{ characterBackground.backstory }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="traits.length" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ t('profileViewer.charSectionTitle') }} CHARACTER</div>
            <div class="fc-block-body">
              <div class="fc-traits">
                <div v-for="tr in traits" :key="tr.key" class="fc-trait">
                  <span class="fc-trait-tag">{{ tr.label }}</span>
                  <span class="fc-trait-desc">{{ tr.value }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="relations.length" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ fieldLabel('relations') }} RELATIONS</div>
            <div class="fc-block-body">
              <div class="fc-relations">
                <div v-for="r in relations" :key="r.name" class="fc-rel-row">
                  <span class="fc-rel-avatar">{{ r.name?.[0] }}</span>
                  <span class="fc-rel-name">{{ r.name }}</span>
                  <span class="fc-rel-desc">{{ r.relationship }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="iconicMoments.length" class="fc-block">
            <div class="fc-block-title"><span>✿</span>NOTES</div>
            <div class="fc-block-body">
              <p v-for="(m, i) in iconicMoments" :key="i" class="fc-note-line">「{{ m }}」</p>
            </div>
          </div>
        </template>

        <!-- 作品 tab -->
        <template v-else>
          <div v-if="worldFacts" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ t('profileViewer.worldSectionTitle') }} WORLD</div>
            <div class="fc-block-body">
              <div class="fc-rows">
                <div v-if="worldSetting?.genre" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('genre') }}</span>
                  <span class="fc-row-val">{{ worldSetting.genre }}</span>
                </div>
                <div v-if="worldSetting?.era" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('era') }}</span>
                  <span class="fc-row-val">{{ worldSetting.era }}</span>
                </div>
                <div v-if="worldSetting?.timeline" class="fc-row">
                  <span class="fc-row-label">{{ fieldLabel('timeline') }}</span>
                  <span class="fc-row-val">{{ worldSetting.timeline }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="worldSetting?.synopsis" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ fieldLabel('synopsis') }} SYNOPSIS</div>
            <div class="fc-block-body">
              <p class="fc-synopsis">{{ worldSetting.synopsis }}</p>
              <div v-if="worldSetting?.themes?.length" class="fc-chips">
                <span v-for="th in worldSetting.themes" :key="th" class="fc-chip">{{ th }}</span>
              </div>
            </div>
          </div>

          <div v-if="worldSetting?.iconic_settings?.length" class="fc-block">
            <div class="fc-block-title"><span>✿</span>{{ fieldLabel('iconic_settings') }}</div>
            <div class="fc-block-body">
              <div class="fc-chips">
                <span v-for="s in worldSetting.iconic_settings" :key="s" class="fc-chip">{{ s }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Right column — persistent regardless of active tab -->
      <div class="fc-right">
        <div class="fc-photo-frame">
          <img v-if="refImageUrl" :src="refImageUrl" class="fc-photo" :alt="character" />
          <div v-else class="fc-photo-empty">{{ character?.[0] }}</div>
          <span class="fc-tape"></span>
          <span v-if="characterBackground?.role" class="fc-role-ribbon">{{ shortRole }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  character: string
  series?: string
  worldSetting?: Record<string, any> | null
  characterBackground?: Record<string, any> | null
  refImageUrl?: string | null
}>()

const { t } = useLocale()
const { fieldLabel } = useFieldLabels()

const activeTab = ref<'char' | 'world'>('char')

const hasProfile = computed(() =>
  !!(props.characterBackground?.role || props.characterBackground?.age || props.characterBackground?.backstory)
)

const worldFacts = computed(() =>
  !!(props.worldSetting?.genre || props.worldSetting?.era || props.worldSetting?.timeline)
)

const TRAIT_KEYS = ['strength', 'weakness', 'surface', 'inner'] as const
const traits = computed(() => {
  const p = props.characterBackground?.personality
  if (!p) return []
  return TRAIT_KEYS
    .filter(k => p[k])
    .map(k => ({ key: k, label: fieldLabel(k), value: p[k] as string }))
})

const relations = computed(() => props.characterBackground?.relations ?? [])
const iconicMoments = computed(() => props.characterBackground?.iconic_moments ?? [])

const shortRole = computed(() => {
  const role = props.characterBackground?.role ?? ''
  return role.split(/[·・]/)[0] || role
})
</script>

<style scoped>
.file-card {
  background: var(--surface-raised);
  border: 3px solid var(--text-hi);
  border-radius: 16px;
  padding: 22px 24px 26px;
  display: flex; flex-direction: column; gap: 16px;
}

.fc-eyebrow {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.6px;
  padding-bottom: 10px; border-bottom: 1px dashed var(--border-md);
}
.fc-eyebrow-mark { color: var(--accent); font-size: 12px; }

.fc-grid {
  display: grid; grid-template-columns: 1.15fr 1fr; gap: 24px;
}
@media (max-width: 640px) {
  .fc-grid { grid-template-columns: 1fr; }
}

.fc-left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.fc-name { font-size: 26px; font-weight: 700; color: var(--text-hi); margin: 0; text-wrap: balance; }
.fc-series { font-size: 12.5px; color: var(--text-accent); margin: 0; }

.fc-tab-nav {
  display: flex; gap: 4px; background: var(--surface-2);
  border-radius: 9px; padding: 3px;
}
.fc-tab-btn {
  flex: 1; padding: 7px 0; border: none; background: transparent; border-radius: 6px;
  font-size: 12px; font-weight: 700; color: var(--text-muted); cursor: pointer;
  transition: background .15s, color .15s;
}
.fc-tab-btn.active { background: var(--surface); color: var(--text-accent); box-shadow: 0 1px 4px var(--shadow); }
.fc-tab-btn:hover:not(.active) { color: var(--text-hi); }

.fc-block {
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 10px;
  overflow: hidden;
}
.fc-block-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 10.5px; font-weight: 700; color: var(--surface);
  text-transform: uppercase; letter-spacing: 0.8px;
  padding: 8px 12px;
  background: var(--text-hi);
}
.fc-block-title span { color: var(--accent); font-size: 11px; }
.fc-block-body { padding: 12px 14px; }

.fc-rows { display: flex; flex-direction: column; }
.fc-row {
  display: flex; gap: 10px; align-items: baseline;
  padding: 7px 0; border-bottom: 1px dashed var(--border-md);
}
.fc-row:last-child { border-bottom: none; padding-bottom: 0; }
.fc-row:first-child { padding-top: 0; }
.fc-row-label {
  font-size: 10px; font-weight: 700; color: var(--text-dim); flex-shrink: 0; width: 44px;
}
.fc-row-val { font-size: 12px; color: var(--text-muted); line-height: 1.6; }

.fc-traits { display: flex; flex-direction: column; }
.fc-trait {
  display: flex; gap: 8px; align-items: baseline;
  padding: 7px 0; border-bottom: 1px dashed var(--border-md);
}
.fc-trait:last-child { border-bottom: none; padding-bottom: 0; }
.fc-trait:first-child { padding-top: 0; }
.fc-trait-tag {
  flex-shrink: 0; font-size: 10.5px; font-weight: 700; color: var(--text-accent);
  background: var(--surface); border: 1px solid var(--border-focus);
  border-radius: 5px; padding: 2px 8px;
}
.fc-trait-desc { font-size: 12px; color: var(--text-muted); line-height: 1.6; }

.fc-relations { display: flex; flex-direction: column; gap: 2px; }
.fc-rel-row {
  display: flex; align-items: center; gap: 8px; padding: 5px 6px; margin: 0 -6px;
  border-radius: 7px; transition: background 0.15s;
}
.fc-rel-row:hover { background: var(--surface); }
.fc-rel-avatar {
  width: 21px; height: 21px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent-dim); color: var(--surface);
  font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.fc-rel-name { font-size: 12px; font-weight: 700; color: var(--text-hi); flex-shrink: 0; }
.fc-rel-desc { font-size: 11px; color: var(--text-dim); }

.fc-synopsis { font-size: 12px; color: var(--text-muted); line-height: 1.75; margin: 0 0 10px; }
.fc-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.fc-chip {
  padding: 3px 9px; background: var(--surface-raised); border: 1px solid var(--border-focus);
  border-radius: 5px; font-size: 10.5px; color: var(--text-accent); font-weight: 600;
}

/* Right column */
.fc-right { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.fc-photo-frame {
  position: relative;
  aspect-ratio: 3 / 4; border-radius: 10px; overflow: hidden;
  background: var(--surface-2); border: 1px solid var(--border-md);
}
.fc-photo { width: 100%; height: 100%; object-fit: cover; display: block; }
.fc-photo-empty {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 48px; font-weight: 700; color: var(--text-ghost, var(--border-focus));
}
.fc-tape {
  position: absolute; top: -6px; right: 22px; width: 54px; height: 20px;
  background: color-mix(in srgb, var(--accent) 30%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
  transform: rotate(6deg);
}
.fc-role-ribbon {
  position: absolute; right: 10px; bottom: 10px;
  background: var(--accent); color: var(--surface);
  font-size: 10.5px; font-weight: 700; padding: 3px 10px; border-radius: 20px;
  transform: rotate(-3deg); box-shadow: 0 3px 10px var(--shadow);
}

.fc-block-body .fc-note-line + .fc-note-line { margin-top: 10px; }
.fc-note-line {
  font-size: 12px; font-style: italic; color: var(--text-muted);
  line-height: 1.7; margin: 0; padding-left: 8px;
  border-left: 2px solid var(--border-focus);
}
</style>
