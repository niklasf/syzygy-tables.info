module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-cssmin');

  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    concat: {
      js: {
        src: ['src/jquery-2.1.3.js', 'src/chess.js', 'src/chessboard-0.3.0.js', 'src/client.js'],
        dest: 'static/client.js'
      },
    },
    uglify: {
      options: {
        compress: true,
        mangle: true,
        sourceMap: true
      },
      build: {
        src: 'static/client.js',
        dest: 'static/client.min.js'
      }
    },
    cssmin: {
      target: {
        files: {
          'static/style.min.css': ['src/bootstrap.css', 'src/chessboard-0.3.0.css', 'src/style.css']
        }
      }
    }
  });

  grunt.registerTask('default', ['concat', 'uglify', 'cssmin']);
};
