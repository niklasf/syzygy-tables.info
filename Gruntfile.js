module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-cssmin');

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
          'static/js/client.min.js': [
            'static/js/jquery-2.1.3.js',
            'static/js/chess.js',
            'static/js/chessboard-0.3.0.js',
            'static/js/client.js'
          ]
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
          'static/css/style.min.css': [
            'static/css/bootstrap.css',
            'static/css/chessboard-0.3.0.css',
            'static/css/style.css'
          ]
        }
      }
    }
  });

  grunt.registerTask('default', ['uglify', 'cssmin']);
};
