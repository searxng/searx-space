module.exports = {
  env: {
    browser: true,
    es6: true
  },
  extends: [
    'plugin:vue/recommended',
    'airbnb-base'
  ],
  globals: {
    Atomics: 'readonly',
    SharedArrayBuffer: 'readonly'
  },
  parserOptions: {
    ecmaVersion: 6,
    sourceType: 'script'
  },
  plugins: [
    'vue'
  ],
  rules: {
    "indent": ["error", 4],
    "no-restricted-syntax": 1,
    "max-len": [ "error", { "code": 120 }],
  }
}
