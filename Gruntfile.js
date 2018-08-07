module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-cssmin');
  grunt.loadNpmTasks('grunt-contrib-watch');

  var js = [
    'static/js/jquery-3.3.1.js',
    'static/js/chess.js',
    'static/js/chessboard-0.3.0.js',
    'static/js/client.js'
  ];

  var css = [
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
    cssmin: {
      options: {
        sourceMap: true,
        keepSpecialComments: 0
      },
      target: {
        files: {
          'static/css/style.min.css': css
        }
      }
    },
    watch: {
      js: {
        files: js,
        tasks: ['uglify']
      },
      css: {
        files: css,
        tasks: ['cssmin']
      }
    }
  });

  grunt.registerTask('default', ['uglify', 'cssmin']);
};
