export function useFieldLabels() {
  const { t } = useLocale()
  function fieldLabel(key: string): string {
    return t(`fields.${key}`)
  }
  return { fieldLabel }
}
