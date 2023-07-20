const gulp = require('gulp');
const cleanCss = require('gulp-clean-css');
const concat = require('gulp-concat');
const rollup = require('rollup').rollup;
const resolve = require('@rollup/plugin-node-resolve').default;
const typescript = require('@rollup/plugin-typescript');
const terser = require('@rollup/plugin-terser');

const css = ['static/css/chessground.css', 'static/css/cburnett.css', 'static/css/style.css'];

gulp.task('css', () =>
  gulp
    .src(css)
    .pipe(
      cleanCss(
        {
          level: {
            1: {
              specialComments: 0,
            },
          },
        },
        details => console.log(`${details.name}: ${details.stats.originalSize} -> ${details.stats.minifiedSize}`),
      ),
    )
    .pipe(concat('style.min.css'))
    .pipe(gulp.dest('static/css')),
);

gulp.task('js', () =>
  rollup({
    input: 'src/client.ts',
    plugins: [
      resolve(),
      typescript({
        noEmitOnError: false,
      }),
      terser({
        safari10: true,
      }),
    ],
  }).then(bundle =>
    bundle.write({
      file: 'static/js/client.min.js',
      format: 'iife',
      sourcemap: true,
    }),
  ),
);

gulp.task('default', gulp.parallel('css', 'js'));
