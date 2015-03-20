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
          'static/client.min.js': ['static/jquery-2.1.3.js', 'static/chess.js', 'static/chessboard-0.3.0.js', 'static/client.js']
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
          'static/style.min.css': ['static/bootstrap.css', 'static/chessboard-0.3.0.css', 'static/style.css']
        }
      }
    }
  });

  grunt.registerTask('default', ['uglify', 'cssmin']);
};
