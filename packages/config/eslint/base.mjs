import js from '@eslint/js';
import tseslint from 'typescript-eslint';

/**
 * Configuration ESLint commune aux packages TypeScript du monorepo.
 * Les applications l'étendent et ajoutent leurs propres plugins.
 */
export default tseslint.config(
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/generated/**'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
      eqeqeq: ['error', 'smart'],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
);
