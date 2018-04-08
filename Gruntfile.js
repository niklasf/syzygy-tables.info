module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-cssmin');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-purifycss');

  var js = [
    'static/js/jquery-3.3.1.js',
    'static/js/chess.js',
    'static/js/chessboard-0.3.0.js',
    'static/js/client.js'
  ];

  var templates = [
    'templates/apidoc.html',
    'templates/index.html',
    'templates/xhr-probe.html',
    'templates/layout.html',
    'templates/legal.html'
  ];

  var unpureCss = [
    'static/css/bootstrap.css'
  ];

  var purifiedCss = 'static/css/purified.css';

  var pureCss = [
    purifiedCss,
    'static/css/chessboard-0.3.0.css',
    'static/css/style.css'
  ];

  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    uglify: {
      options: {
        compress: true,
        mangle: true,
        sourceMap: true
      },
      target: {
        files: {
          'static/js/client.min.js': js
        }
      }
    },
    purifycss: {
      target: {
        src: js.concat(templates),
        css: unpureCss,
        dest: purifiedCss
      }
    },
    cssmin: {
      options: {
        sourceMap: true,
        keepSpecialComments: 0
      },
      target: {
        files: {
          'static/css/style.min.css': pureCss
        }
      }
    },
    watch: {
      js: {
        files: js,
        tasks: ['uglify']
      },
      unpureCss: {
        files: unpureCss,
        tasks: ['purifycss'],
      },
      pureCss: {
        files: pureCss,
        tasks: ['cssmin']
      }
    }
  });

  grunt.registerTask('default', ['uglify', 'purifycss', 'cssmin']);
};
