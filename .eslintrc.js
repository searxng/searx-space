module.exports = {
  env: {
    browser: true,
    es6: true
  },
  extends: [
    'airbnb-base'
  ],
  parserOptions: {
    ecmaVersion: 6,
    sourceType: 'script'
  },
  rules: {
    "indent": ["error", 4],
    "no-restricted-syntax": 1,
    "max-len": [ "error", { "code": 120 }],
  }
}
