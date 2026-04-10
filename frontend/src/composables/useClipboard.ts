import { copyToClipboard, Notify } from 'quasar';

export function useClipboard() {
  /**
   * copies text to clipboard and provides visual/auditory feedback
   * @param text The string to copy
   * @param element Optional HTML element to apply a flash effect to
   */
  const copyText = async (text: string, element?: HTMLElement | null): Promise<boolean> => {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for non-secure contexts or older browsers via Quasar util
        await copyToClipboard(text);
      }

      // Visual feedback
      if (element) {
        element.classList.add('flash-indicator');
        setTimeout(() => element.classList.remove('flash-indicator'), 300);
      }

      Notify.create({
        message: 'COPIED TO CLIPBOARD',
        color: 'indigo-10',
        textColor: 'primary',
        position: 'bottom',
        timeout: 1000,
        classes: 'text-mono text-caption'
      });

      return true;
    } catch (err) {
      console.error('Failed to copy text: ', err);
      return false;
    }
  };

  return { copyText };
}
