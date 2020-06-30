const gulp = require('gulp');
const cleanCss = require('gulp-clean-css');
const concat = require('gulp-concat');
const rollup = require('rollup');
const resolve = require('@rollup/plugin-node-resolve').default;
const commonjs = require('@rollup/plugin-commonjs');
const babel = require('@rollup/plugin-babel').babel;
const terser = require('rollup-plugin-terser').terser;

const css = [
  'static/css/chessground.css',
  'static/css/cburnett.css',
  'static/css/style.css',
];

gulp.task('css', () => gulp.src(css)
  .pipe(cleanCss({
    level: {
      1: {
        specialComments: 0,
      },
    },
  }, details => console.log(`${details.name}: ${details.stats.originalSize} -> ${details.stats.minifiedSize}`)))
  .pipe(concat('style.min.css'))
  .pipe(gulp.dest('static/css'))
);

gulp.task('js', () => rollup.rollup({
  input: 'src/client.js',
  plugins: [
    commonjs(),
    resolve(),
    babel({
      babelHelpers: 'bundled',
      presets: ['@babel/env'],
    }),
    terser({
      safari10: true,
    }),
  ],
}).then(bundle => bundle.write({
  file: 'static/js/client.min.js',
  format: 'iife',
  sourcemap: true,
})));

gulp.task('default', gulp.parallel('css', 'js'));
