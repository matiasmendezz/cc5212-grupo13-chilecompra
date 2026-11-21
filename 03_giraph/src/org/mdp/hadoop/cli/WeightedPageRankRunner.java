package org.mdp.hadoop.cli;

import org.apache.giraph.GiraphRunner;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.util.ToolRunner;

import org.mdp.hadoop.io.TextDoubleTextEdgeInputFormat;
import org.mdp.hadoop.io.VertexValueTextOutputFormat;
import org.mdp.hadoop.pr.PageRankAgg;

/** Uso: WeightedPageRankRunner <entrada> <salida> <workers> */
public class WeightedPageRankRunner {

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.err.println("Uso: WeightedPageRankRunner <entrada> <salida> <workers>");
            System.exit(1);
        }
        String input = args[0];
        String output = args[1];
        String workers = args[2];

        // Se borra la salida si ya existe
        Configuration conf = new Configuration();
        Path outPath = new Path(output);
        FileSystem fs = FileSystem.get(conf);
        if (fs.exists(outPath)) {
            fs.delete(outPath, true);
        }

        String[] giraphArgs = {
            WeightedPageRank.class.getName(),
            "-eif", TextDoubleTextEdgeInputFormat.class.getName(),
            "-eip", input,
            "-vof", VertexValueTextOutputFormat.class.getName(),
            "-op", output,
            "-w", workers,
            "-ca", "mapreduce.job.tracker=yarn",
            "-ca", "mapreduce.framework.name=yarn",
            "-mc", PageRankAgg.class.getName()
        };

        int res = ToolRunner.run(conf, new GiraphRunner(), giraphArgs);
        if (res != 0) {
            System.exit(res);
        }
    }
}
